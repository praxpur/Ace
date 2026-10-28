import unittest

from treehouse.selection import PlaybackDraft


def catalogs(prefix='old', signature='stable'):
    return [{'key': 'course-a', 'course': {'label': '同名课程', 'detail': '共享课'},
             'videos': [{'key': prefix + ':a', 'label': '绪论', 'signature': signature,
                         'completed': False}]},
            {'key': 'course-b', 'course': {'label': '同名课程', 'detail': 'AI智课'},
             'videos': [{'key': prefix + ':b', 'label': '绪论', 'signature': 'stable',
                         'completed': False}]}]


class PlaybackDraftTests(unittest.TestCase):
    def test_new_catalog_requires_explicit_video_selection(self):
        draft = PlaybackDraft()
        draft.load(catalogs())
        self.assertEqual(draft.ordered_keys(), [])

    def test_switching_courses_preserves_other_courses_choices(self):
        draft = PlaybackDraft()
        draft.load(catalogs())
        draft.update_current(['old:a'])
        draft.current = 'course-b'
        draft.update_current(['old:b'])
        self.assertEqual(draft.ordered_keys(), ['old:a', 'old:b'])
        self.assertEqual(draft.course_count, 2)
        draft.update_current([])
        self.assertEqual(draft.ordered_keys(), ['old:a'])

    def test_rescan_restores_identity_and_rejects_changed_video(self):
        draft = PlaybackDraft()
        draft.load(catalogs())
        draft.selected = {'old:a', 'old:b'}
        draft.load(catalogs('new', 'changed-content'))
        self.assertEqual(draft.ordered_keys(), ['new:b'])

    def test_completed_or_unknown_status_is_never_restored_automatically(self):
        draft = PlaybackDraft()
        draft.load(catalogs())
        draft.selected = {'old:a', 'old:b'}
        fresh = catalogs('new')
        fresh[0]['videos'][0]['completed'] = True
        fresh[1]['videos'][0]['completed'] = None
        draft.load(fresh)
        self.assertEqual(draft.ordered_keys(), [])
        # A user may still explicitly choose a completed item.
        draft.update_current(['new:a'])
        self.assertEqual(draft.ordered_keys(), ['new:a'])
        draft.load(catalogs('again'))
        self.assertEqual(draft.ordered_keys(), ['again:a'])

    def test_removed_courses_and_unknown_keys_do_not_enter_queue(self):
        draft = PlaybackDraft()
        draft.load(catalogs())
        draft.update_current(['old:a', 'not-a-video'])
        draft.load(catalogs('new')[1:])
        self.assertEqual(draft.ordered_keys(), [])

    def test_ambiguous_duplicates_are_not_silently_selected_on_rescan(self):
        draft = PlaybackDraft()
        old = catalogs()[:1]
        draft.load(old)
        draft.update_current(['old:a'])
        fresh = catalogs('new')[:1]
        fresh[0]['videos'].append({**fresh[0]['videos'][0], 'key': 'new:duplicate'})
        draft.load(fresh)
        self.assertEqual(draft.ordered_keys(), [])

    def test_queue_uses_catalog_order_instead_of_click_order(self):
        draft = PlaybackDraft()
        draft.load(catalogs())
        draft.current = 'course-b'
        draft.update_current(['old:b'])
        draft.current = 'course-a'
        draft.update_current(['old:a'])
        self.assertEqual(draft.ordered_keys(), ['old:a', 'old:b'])
