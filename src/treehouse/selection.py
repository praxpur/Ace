"""A playback draft: browsing a course never loses another course's choices."""
from dataclasses import dataclass, field
from collections import Counter


def video_identity(group, video):
    course = group.get('course') or {}
    return (course.get('label', ''), course.get('detail', ''),
            video['label'], video.get('detail', ''), video.get('signature', ''))


@dataclass
class PlaybackDraft:
    groups: list = field(default_factory=list)
    selected: set = field(default_factory=set)
    current: str | None = None

    def load(self, groups):
        previous_counts = Counter(video_identity(group, video) for group in self.groups
                                  for video in group['videos'])
        previous = {video_identity(group, video) for group in self.groups
                    for video in group['videos'] if video['key'] in self.selected
                    and previous_counts[video_identity(group, video)] == 1}
        new_counts = Counter(video_identity(group, video) for group in groups
                             for video in group['videos'])
        self.groups = groups
        self.selected = {video['key'] for group in groups for video in group['videos']
                         if video_identity(group, video) in previous
                         and new_counts[video_identity(group, video)] == 1
                         and video.get('completed') is False}
        self.current = next((g['key'] for g in groups if g['videos']),
                            groups[0]['key'] if groups else None)

    @property
    def current_group(self):
        return next((group for group in self.groups if group['key'] == self.current), None)

    def update_current(self, keys):
        group = self.current_group
        if group:
            available = {row['key'] for row in group['videos']}
            self.selected.difference_update(available)
            self.selected.update(set(keys) & available)

    def ordered_keys(self):
        return [video['key'] for group in self.groups for video in group['videos']
                if video['key'] in self.selected]

    @property
    def course_count(self):
        return sum(any(v['key'] in self.selected for v in g['videos']) for g in self.groups)
