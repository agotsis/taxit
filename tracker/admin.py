from django.contrib import admin
from .models import State, Office, Day, RatioView


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ["name", "abbreviation", "day_threshold", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "abbreviation"]
    ordering = ["name"]


@admin.register(Office)
class OfficeAdmin(admin.ModelAdmin):
    list_display = ["name", "state", "latitude", "longitude"]
    list_filter = ["state"]
    search_fields = ["name", "address"]


@admin.register(Day)
class DayAdmin(admin.ModelAdmin):
    list_display = ["date", "day_type", "get_states", "office", "note_preview"]
    list_filter = ["day_type", "states", "office"]
    search_fields = ["note"]
    date_hierarchy = "date"
    filter_horizontal = ["states"]
    ordering = ["-date"]

    def get_states(self, obj):
        return ", ".join(s.abbreviation for s in obj.states.all())

    get_states.short_description = "States"

    def note_preview(self, obj):
        return obj.note[:50] + "..." if len(obj.note) > 50 else obj.note

    note_preview.short_description = "Note"


@admin.register(RatioView)
class RatioViewAdmin(admin.ModelAdmin):
    list_display = ["name", "start_date", "end_date", "days_in_range", "created_at"]
    search_fields = ["name", "description"]
    ordering = ["start_date", "end_date"]
    actions = ["make_copy"]
    change_form_template = "admin/tracker/ratioview/change_form.html"

    @admin.action(description="Make a copy of selected ratio views")
    def make_copy(self, request, queryset):
        copied_count = 0
        for ratio_view in queryset:
            ratio_view.pk = None
            ratio_view.id = None
            ratio_view.name = f"{ratio_view.name} (Copy)"
            ratio_view.save()
            copied_count += 1

        self.message_user(
            request,
            f"Successfully created {copied_count} copy/copies.",
        )

    make_copy.short_description = "Make a copy of selected ratio views"
