"""Pod level scheduler.

Each pod can run `max_activity` activities at the same time (one per workstream). Each
activity takes `expected_roadmap_days` calendar days. A min-heap per pod keeps the running
activities ordered by end date. When the earliest activity ends, its slot is freed, the
activity counts as enabled (so later activities can get shorter), and the pod starts the next
activity in priority order.
"""
from __future__ import annotations

import heapq
from datetime import timedelta

import pandas as pd

from .config import Config
from .durations import calculate_expected_time_taken

DATE_FMT = "%d %b %Y"
KEY = ["use_case_id", "project_id", "data_source_id"]


class PodScheduler:
    def __init__(self, project_source: pd.DataFrame, data_sources: pd.DataFrame, config: Config):
        self.project_source = project_source
        self.data_sources = data_sources
        self.config = config
        # snapshot used for the first round of assignments
        self.activities = project_source.to_dict("records")
        pods = project_source["pod_name"].unique()
        self.teams = {pod: [] for pod in pods}                 # pod -> heap of running activities
        self.team_activity_count = {pod: 0 for pod in pods}    # pod -> running activities
        self.freed_workstreams = {pod: [] for pod in pods}     # pod -> workstreams free for reuse
        self.scheduled_activities = set()

    # ------------------------------------------------------------------ helpers
    def _refresh_durations(self):
        self.project_source = calculate_expected_time_taken(self.project_source, self.data_sources, self.config)

    def _index_of(self, ids):
        use_case_id, project_id, data_source_id = ids
        return (
            (self.project_source["use_case_id"] == use_case_id)
            & (self.project_source["project_id"] == project_id)
            & (self.project_source["data_source_id"] == data_source_id)
        )

    def _book(self, activity, team, start, end, duration, workstream):
        """Write the booking back to project_sources and return the schedule row."""
        ids = (activity["use_case_id"], activity["project_id"], activity["data_source_id"])
        self.project_source.loc[
            self._index_of(ids), ["start_date", "end_date", "actual_roadmap_days", "workstream"]
        ] = [start.strftime(DATE_FMT), end.strftime(DATE_FMT), duration, workstream]
        return {
            "Activity": ids,
            "Team": team,
            "Actual_Days": duration,
            "start_date": start.strftime(DATE_FMT),
            "end_date": end.strftime(DATE_FMT),
            "Workstream": workstream,
        }

    # ------------------------------------------------------------------ first round
    def assign_activities(self):
        """Fill every pod up to its capacity, in priority order, starting on the pod start date."""
        schedule = []
        workstream_counter = {}
        self._refresh_durations()
        planned = [a for a in self.activities if a["processed_datasource_status"] == "planned"]
        done_pairs = {(u, d) for u, _, d in self.scheduled_activities}
        todo = [a for a in planned if (a["use_case_id"], a["data_source_id"]) not in done_pairs]
        ordered = sorted(todo, key=lambda x: (x["use_case_priority_sequence"], x["expected_roadmap_days"]))
        for activity in ordered:
            team = activity["pod_name"]
            if team not in workstream_counter:
                workstream_counter[team] = 0
            ids = (activity["use_case_id"], activity["project_id"], activity["data_source_id"])
            start = self.config.get_pod_start_date(team)
            max_activities = self.config.get_pod_max_activity(team)
            if self.team_activity_count[team] < max_activities and ids not in self.scheduled_activities:
                workstream_counter[team] += 1
                workstream = f"workstream{workstream_counter[team]}"
                duration = activity["expected_roadmap_days"]
                end = start + timedelta(days=duration)
                heapq.heappush(self.teams[team], (end, duration, ids, workstream))
                self.scheduled_activities.add(ids)
                self.team_activity_count[team] += 1
                if workstream_counter[team] == max_activities:
                    workstream_counter[team] = 1
                schedule.append(self._book(activity, team, start, end, duration, workstream))
        return schedule

    # ------------------------------------------------------------------ main loop
    def dynamic_scheduling(self):
        """Run the full plan: first round for every pod, then free slots as activities end."""
        schedule = []
        for _ in self.teams.keys():
            self._refresh_durations()
            schedule.extend(self.assign_activities())
        while any(self.team_activity_count.values()):
            earliest_end = min([queue[0][0] for queue in self.teams.values() if queue])
            finished = []
            for team, queue in self.teams.items():
                while queue and queue[0][0] == earliest_end:
                    end, duration, ids, workstream = heapq.heappop(queue)
                    finished.append((team, end, duration, ids, workstream))
                    self.team_activity_count[team] -= 1
                    self.freed_workstreams[team].append(workstream)
            for _, _, _, ids, _ in finished:
                self.project_source.loc[self._index_of(ids), "processed_datasource_status"] = "enabled"
            self._refresh_durations()
            active_ids = {item[2] for pod_queue in self.teams.values() for item in pod_queue}
            zero_days = (
                (self.project_source["expected_roadmap_days"] == 0)
                & (self.project_source["processed_datasource_status"] == "planned")
                & ~self.project_source.set_index(KEY).index.isin(active_ids)
            )
            self.project_source.loc[zero_days, "actual_roadmap_days"] = 0
            self.project_source.loc[zero_days, "start_date"] = earliest_end.strftime(DATE_FMT)
            self.project_source.loc[zero_days, "end_date"] = earliest_end.strftime(DATE_FMT)
            self.project_source.loc[zero_days, "processed_datasource_status"] = "enabled"
            for team, _, _, _, _ in finished:
                if self.team_activity_count[team] < self.config.get_pod_max_activity(team):
                    schedule.extend(self.assign_new_activity(team, earliest_end))
        return schedule

    def assign_new_activity(self, team, current_date):
        """Start the next planned activities of `team` on `current_date`, up to its capacity."""
        new_schedule = []
        done_pairs = {(u, d) for u, _, d in self.scheduled_activities}
        candidates = self.project_source[
            (self.project_source["pod_name"] == team)
            & (self.project_source["processed_datasource_status"] == "planned")
            & ~self.project_source.set_index(KEY).index.isin(self.scheduled_activities)
        ].sort_values(by=["use_case_priority_sequence", "expected_roadmap_days"]).to_dict("records")
        candidates = [a for a in candidates if (a["use_case_id"], a["data_source_id"]) not in done_pairs]
        max_activities = self.config.get_pod_max_activity(team)
        for activity in candidates:
            ids = (activity["use_case_id"], activity["project_id"], activity["data_source_id"])
            if self.team_activity_count[team] < max_activities and ids not in self.scheduled_activities:
                start = max(current_date, self.config.get_pod_start_date(team))
                duration = activity["expected_roadmap_days"]
                end = start + timedelta(days=duration)
                if self.freed_workstreams[team]:
                    workstream = self.freed_workstreams[team].pop(0)
                else:
                    workstream = f"workstream{self.team_activity_count[team] + 1}"
                heapq.heappush(self.teams[team], (end, duration, ids, workstream))
                self.scheduled_activities.add(ids)
                self.team_activity_count[team] += 1
                new_schedule.append(self._book(activity, team, start, end, duration, workstream))
        return new_schedule
