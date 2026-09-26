# Create your tests here.
from datetime import date

from django.test import TestCase
from django.urls import reverse

from .models import Day, Office, State
from .views import active_states_by_frequency


class EditDayTests(TestCase):
    def setUp(self):
        self.state = State.objects.create(
            name="New York", abbreviation="NY", day_threshold=183, is_active=True
        )
        self.office = Office.objects.create(
            name="New York Office",
            latitude=40.7128,
            longitude=-74.0060,
            state=self.state,
        )

    def test_update_derives_state_from_office(self):
        response = self.client.post(
            reverse("day_update", args=["2026-09-26"]),
            {"day_type": Day.DayType.STANDARD_WORKDAY, "office": self.office.pk},
        )

        self.assertEqual(response.status_code, 200)
        day = Day.objects.get(date=date(2026, 9, 26))
        self.assertEqual(day.office, self.office)
        self.assertQuerySetEqual(day.states.all(), [self.state])

    def test_bulk_edit_derives_state_from_office(self):
        response = self.client.post(
            reverse("day_bulk_edit"),
            {
                "start_date": "2026-09-22",
                "end_date": "2026-09-23",
                "office": self.office.pk,
            },
        )

        self.assertRedirects(response, reverse("year_view", args=[2026]))
        days = Day.objects.filter(date__range=[date(2026, 9, 22), date(2026, 9, 23)])
        self.assertEqual(days.count(), 2)
        for day in days:
            self.assertEqual(day.office, self.office)
            self.assertQuerySetEqual(day.states.all(), [self.state])

    def test_active_states_are_sorted_by_usage_then_name(self):
        less_used = State.objects.create(
            name="California", abbreviation="CA", day_threshold=183, is_active=True
        )
        unused = State.objects.create(
            name="Alabama", abbreviation="AL", day_threshold=183, is_active=True
        )
        first_day = Day.objects.create(date=date(2026, 9, 25))
        first_day.states.add(self.state)
        second_day = Day.objects.create(date=date(2026, 9, 24))
        second_day.states.add(self.state, less_used)

        expected = [self.state, less_used, unused]
        self.assertQuerySetEqual(active_states_by_frequency(), expected)

        response = self.client.get(reverse("day_bulk_edit"))
        self.assertQuerySetEqual(response.context["states"], expected)
