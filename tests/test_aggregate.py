import datetime
import os
import sys
import unittest
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aggregate import aggregate
from parser import ParsedPhoto
from roster import Roster

EASTERN = ZoneInfo("America/New_York")


def make_roster(exclusions=None, late_upload_deadline=None, flagged_overrides=None):
    return Roster(
        teams=[["Maddy", "Glenn"]],
        name_lookup={"maddy": "Maddy", "glenn": "Glenn"},
        alias_lookup={},
        person_to_team={"Maddy": 0, "Glenn": 0},
        adjustments={},
        exclusions=exclusions or [],
        late_upload_deadline=late_upload_deadline,
        flagged_overrides=flagged_overrides or [],
    )


def make_photo(filename, person, date, department="Unknown", filename_date=None, mtime=0.0):
    return ParsedPhoto(
        filename=filename,
        person=person,
        unmatched_guess=None,
        department=department,
        date=date,
        date_from_filename=True,
        dedup_key=(person, filename.lower()),
        filename_date=filename_date,
        mtime=mtime,
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


DEADLINE = {"cutoff_hour": 12, "timezone": "America/New_York"}


def eastern_mtime(year, month, day, hour, minute=0):
    return datetime.datetime(year, month, day, hour, minute, tzinfo=EASTERN).timestamp()


class TestAggregateLateUploads(unittest.TestCase):
    def test_uploaded_before_noon_next_day_counts(self):
        roster = make_roster(late_upload_deadline=DEADLINE)
        photo = make_photo(
            "2026-08-04 - Maddy - Bunk IMG_1.jpg", "Maddy", "8/4",
            filename_date=datetime.date(2026, 8, 4),
            mtime=eastern_mtime(2026, 8, 5, 11, 59),
        )
        result = aggregate([photo], roster)
        self.assertEqual(result.total_late, 0)
        self.assertEqual(result.teams[0].counts["Maddy"], 1)

    def test_uploaded_exactly_at_noon_next_day_counts(self):
        roster = make_roster(late_upload_deadline=DEADLINE)
        photo = make_photo(
            "2026-08-04 - Maddy - Bunk IMG_2.jpg", "Maddy", "8/4",
            filename_date=datetime.date(2026, 8, 4),
            mtime=eastern_mtime(2026, 8, 5, 12, 0),
        )
        result = aggregate([photo], roster)
        self.assertEqual(result.total_late, 0)
        self.assertEqual(result.teams[0].counts["Maddy"], 1)

    def test_uploaded_after_noon_next_day_is_late(self):
        roster = make_roster(late_upload_deadline=DEADLINE)
        photo = make_photo(
            "2026-08-04 - Maddy - Bunk IMG_3.jpg", "Maddy", "8/4",
            filename_date=datetime.date(2026, 8, 4),
            mtime=eastern_mtime(2026, 8, 5, 12, 1),
        )
        result = aggregate([photo], roster)
        self.assertEqual(result.total_late, 1)
        self.assertEqual(result.teams[0].counts["Maddy"], 0)

    def test_uploaded_days_later_is_late(self):
        roster = make_roster(late_upload_deadline=DEADLINE)
        photo = make_photo(
            "2026-08-04 - Maddy - Bunk IMG_4.jpg", "Maddy", "8/4",
            filename_date=datetime.date(2026, 8, 4),
            mtime=eastern_mtime(2026, 8, 10, 9, 0),
        )
        result = aggregate([photo], roster)
        self.assertEqual(result.total_late, 1)

    def test_no_deadline_configured_never_flags_late(self):
        roster = make_roster(late_upload_deadline=None)
        photo = make_photo(
            "2026-08-04 - Maddy - Bunk IMG_5.jpg", "Maddy", "8/4",
            filename_date=datetime.date(2026, 8, 4),
            mtime=eastern_mtime(2026, 8, 10, 9, 0),
        )
        result = aggregate([photo], roster)
        self.assertEqual(result.total_late, 0)
        self.assertEqual(result.teams[0].counts["Maddy"], 1)

    def test_missing_filename_date_never_flags_late(self):
        # Fallback-to-mtime dates carry no year, so a deadline can't be computed.
        roster = make_roster(late_upload_deadline=DEADLINE)
        photo = make_photo(
            "Maddy Bunk IMG_6.jpg", "Maddy", "8/4",
            filename_date=None,
            mtime=eastern_mtime(2026, 8, 10, 9, 0),
        )
        result = aggregate([photo], roster)
        self.assertEqual(result.total_late, 0)
        self.assertEqual(result.teams[0].counts["Maddy"], 1)


class TestAggregateEffectiveFrom(unittest.TestCase):
    DEADLINE_WITH_CUTOFF = {
        "cutoff_hour": 12,
        "timezone": "America/New_York",
        "effective_from": "2026-08-05T15:00:00-04:00",
    }

    def test_late_upload_before_effective_from_is_grandfathered_in(self):
        roster = make_roster(late_upload_deadline=self.DEADLINE_WITH_CUTOFF)
        photo = make_photo(
            "2026-08-01 - Maddy - Bunk IMG_1.jpg", "Maddy", "8/1",
            filename_date=datetime.date(2026, 8, 1),
            mtime=eastern_mtime(2026, 8, 4, 20, 0),  # very late by the rule, but pre-cutoff
        )
        result = aggregate([photo], roster)
        self.assertEqual(result.total_late, 0)
        self.assertEqual(result.teams[0].counts["Maddy"], 1)

    def test_late_upload_after_effective_from_is_still_caught(self):
        roster = make_roster(late_upload_deadline=self.DEADLINE_WITH_CUTOFF)
        photo = make_photo(
            "2026-08-05 - Maddy - Bunk IMG_2.jpg", "Maddy", "8/5",
            filename_date=datetime.date(2026, 8, 5),
            mtime=eastern_mtime(2026, 8, 6, 12, 1),  # after cutoff, and genuinely late
        )
        result = aggregate([photo], roster)
        self.assertEqual(result.total_late, 1)
        self.assertEqual(result.teams[0].counts["Maddy"], 0)

    def test_bad_date_before_effective_from_is_also_grandfathered_in(self):
        # The whole rule is bypassed pre-cutoff, including the flagging check.
        roster = make_roster(late_upload_deadline=self.DEADLINE_WITH_CUTOFF)
        photo = make_photo(
            "2023-01-31 - Maddy Nash - EVAC C73A9999.JPG", "Maddy", "1/31",
            filename_date=datetime.date(2023, 1, 31),
            mtime=eastern_mtime(2026, 8, 5, 10, 0),  # before the 3pm cutoff
        )
        result = aggregate([photo], roster)
        self.assertEqual(result.total_flagged, 0)
        self.assertEqual(result.total_late, 0)
        self.assertEqual(result.teams[0].counts["Maddy"], 1)


class TestAggregateFlaggedDates(unittest.TestCase):
    def test_filename_year_mismatch_is_flagged_not_late(self):
        roster = make_roster(late_upload_deadline=DEADLINE)
        photo = make_photo(
            "2023-01-31 - Maddy Nash - EVAC C73A0027.JPG", "Maddy", "1/31",
            filename_date=datetime.date(2023, 1, 31),
            mtime=eastern_mtime(2026, 8, 4, 14, 24),
        )
        result = aggregate([photo], roster)
        self.assertEqual(result.total_flagged, 1)
        self.assertEqual(result.total_late, 0)
        self.assertEqual(result.teams[0].counts["Maddy"], 0)

    def test_flagged_photo_not_counted_and_not_excluded(self):
        roster = make_roster(late_upload_deadline=DEADLINE)
        photo = make_photo(
            "2023-01-31 - Maddy Nash - EVAC C73A0027.JPG", "Maddy", "1/31",
            filename_date=datetime.date(2023, 1, 31),
            mtime=eastern_mtime(2026, 8, 4, 14, 24),
        )
        result = aggregate([photo], roster)
        self.assertEqual(result.total_excluded, 0)
        self.assertEqual(result.total_matched, 0)

    def test_explicit_exclusion_rule_takes_precedence_over_flagging(self):
        # A reviewed/confirmed exclusion rule should catch it before the
        # flag-for-review check ever runs, since it's already been decided.
        roster = make_roster(
            exclusions=[{"person": "Maddy", "date": "1/31", "filename_contains": "evac"}],
            late_upload_deadline=DEADLINE,
        )
        photo = make_photo(
            "2023-01-31 - Maddy Nash - EVAC C73A0027.JPG", "Maddy", "1/31",
            filename_date=datetime.date(2023, 1, 31),
            mtime=eastern_mtime(2026, 8, 4, 14, 24),
        )
        result = aggregate([photo], roster)
        self.assertEqual(result.total_excluded, 1)
        self.assertEqual(result.total_flagged, 0)

    def test_same_year_late_upload_still_treated_as_late_not_flagged(self):
        roster = make_roster(late_upload_deadline=DEADLINE)
        photo = make_photo(
            "2026-08-04 - Maddy - Bunk IMG_9.jpg", "Maddy", "8/4",
            filename_date=datetime.date(2026, 8, 4),
            mtime=eastern_mtime(2026, 8, 5, 12, 1),
        )
        result = aggregate([photo], roster)
        self.assertEqual(result.total_late, 1)
        self.assertEqual(result.total_flagged, 0)


class TestAggregateFlaggedOverrides(unittest.TestCase):
    def test_matching_override_counts_normally_despite_bad_date(self):
        roster = make_roster(
            late_upload_deadline=DEADLINE,
            flagged_overrides=[{"person": "Maddy", "date": "2/13", "filename_contains": "skatepark"}],
        )
        photo = make_photo(
            "2015-02-13 - Maddy Nash - Skatepark P1260057 copy.JPG", "Maddy", "2/13",
            filename_date=datetime.date(2015, 2, 13),
            mtime=eastern_mtime(2026, 8, 6, 10, 0),
        )
        result = aggregate([photo], roster)
        self.assertEqual(result.total_flagged, 0)
        self.assertEqual(result.total_late, 0)
        self.assertEqual(result.teams[0].counts["Maddy"], 1)

    def test_non_matching_override_still_gets_flagged(self):
        roster = make_roster(
            late_upload_deadline=DEADLINE,
            flagged_overrides=[{"person": "Maddy", "date": "2/13", "filename_contains": "skatepark"}],
        )
        photo = make_photo(
            "2015-02-13 - Maddy Nash - EVAC P9999999.JPG", "Maddy", "2/13",
            filename_date=datetime.date(2015, 2, 13),
            mtime=eastern_mtime(2026, 8, 6, 10, 0),
        )
        result = aggregate([photo], roster)
        self.assertEqual(result.total_flagged, 1)
        self.assertEqual(result.teams[0].counts["Maddy"], 0)


if __name__ == "__main__":
    unittest.main()
