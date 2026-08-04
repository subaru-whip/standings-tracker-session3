import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aggregate import aggregate
from parser import ParsedPhoto
from roster import Roster


def make_roster(exclusions):
    return Roster(
        teams=[["Maddy", "Glenn"]],
        name_lookup={"maddy": "Maddy", "glenn": "Glenn"},
        alias_lookup={},
        person_to_team={"Maddy": 0, "Glenn": 0},
        adjustments={},
        exclusions=exclusions,
    )


def make_photo(filename, person, date, department="Unknown"):
    return ParsedPhoto(
        filename=filename,
        person=person,
        unmatched_guess=None,
        department=department,
        date=date,
        date_from_filename=True,
        dedup_key=(person, filename.lower()),
    )


class TestAggregateExclusions(unittest.TestCase):
    def test_matching_person_date_and_filename_substring_is_excluded(self):
        roster = make_roster([{"person": "Maddy", "date": "8/3", "filename_contains": "evac"}])
        photos = [make_photo("2026-08-03 - Maddy Nash - EVAC IMG_1.jpg", "Maddy", "8/3")]
        result = aggregate(photos, roster)
        self.assertEqual(result.total_excluded, 1)
        self.assertEqual(result.total_matched, 0)
        team = result.teams[0]
        self.assertEqual(team.counts["Maddy"], 0)

    def test_filename_substring_match_is_case_insensitive(self):
        roster = make_roster([{"person": "Maddy", "date": "8/3", "filename_contains": "evac"}])
        photos = [make_photo("2026-08-03 - Maddy Nash - evac IMG_2.jpg", "Maddy", "8/3")]
        result = aggregate(photos, roster)
        self.assertEqual(result.total_excluded, 1)

    def test_other_person_same_date_and_word_not_excluded(self):
        roster = make_roster([{"person": "Maddy", "date": "8/3", "filename_contains": "evac"}])
        photos = [make_photo("2026-08-03 - Glenn - EVAC IMG_3.jpg", "Glenn", "8/3")]
        result = aggregate(photos, roster)
        self.assertEqual(result.total_excluded, 0)
        self.assertEqual(result.teams[0].counts["Glenn"], 1)

    def test_same_person_different_date_not_excluded(self):
        roster = make_roster([{"person": "Maddy", "date": "8/3", "filename_contains": "evac"}])
        photos = [make_photo("2026-08-04 - Maddy Nash - EVAC IMG_4.jpg", "Maddy", "8/4")]
        result = aggregate(photos, roster)
        self.assertEqual(result.total_excluded, 0)
        self.assertEqual(result.teams[0].counts["Maddy"], 1)

    def test_same_person_and_date_without_keyword_not_excluded(self):
        roster = make_roster([{"person": "Maddy", "date": "8/3", "filename_contains": "evac"}])
        photos = [make_photo("2026-08-03 - Maddy Nash - Bunk IMG_5.jpg", "Maddy", "8/3")]
        result = aggregate(photos, roster)
        self.assertEqual(result.total_excluded, 0)
        self.assertEqual(result.teams[0].counts["Maddy"], 1)


if __name__ == "__main__":
    unittest.main()
