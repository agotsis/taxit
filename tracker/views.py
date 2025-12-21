from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Q
from django.conf import settings
from datetime import datetime, date, timedelta
from .models import Day, State, Office, RatioView


def year_view(request, year=None):
    """Display days and state counts for a specific year."""
    if year is None:
        year = datetime.now().year
    
    start_date = date(year, 1, 1)
    end_date = date(year, 12, 31)
    
    days = Day.objects.filter(date__range=[start_date, end_date]).prefetch_related('states', 'office')
    
    states = State.objects.all()
    state_counts = {}
    for state in states:
        count = days.filter(states=state).count()
        if count > 0:
            state_counts[state] = {
                'count': count,
                'threshold': state.day_threshold,
                'percentage': (count / state.day_threshold * 100) if state.day_threshold > 0 else 0
            }
    
    context = {
        'year': year,
        'days': days,
        'state_counts': state_counts,
        'states': states,
        'settings': settings,
    }
    return render(request, 'tracker/year_view.html', context)


def day_bulk_edit(request):
    """Bulk edit days - add states to multiple days at once."""
    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        state_ids = request.POST.getlist('states')
        day_type = request.POST.get('day_type')
        office_id = request.POST.get('office')
        weekdays = request.POST.getlist('weekdays')
        
        if start_date and end_date and state_ids:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            states = State.objects.filter(id__in=state_ids)
            
            current = start
            days_updated = 0
            while current <= end:
                if not weekdays or str(current.weekday()) in weekdays:
                    day, created = Day.objects.get_or_create(date=current)
                    
                    if day_type:
                        day.day_type = day_type
                    if office_id:
                        day.office_id = office_id if office_id != '' else None
                    day.save()
                    
                    day.states.add(*states)
                    days_updated += 1
                
                current += timedelta(days=1)
            
            messages.success(request, f'Updated {days_updated} days')
            return redirect('year_view', year=start.year)
    
    states = State.objects.all()
    offices = Office.objects.all()
    day_types = Day.DayType.choices
    weekday_choices = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')
    ]
    
    context = {
        'states': states,
        'offices': offices,
        'day_types': day_types,
        'weekday_choices': weekday_choices,
        'settings': settings,
    }
    return render(request, 'tracker/day_bulk_edit.html', context)


def office_list(request):
    """List all offices."""
    offices = Office.objects.select_related('state').all()
    context = {'offices': offices, 'settings': settings}
    return render(request, 'tracker/office_list.html', context)


def ratio_view_list(request):
    """List all ratio views."""
    ratio_views = RatioView.objects.all()
    context = {'ratio_views': ratio_views, 'settings': settings}
    return render(request, 'tracker/ratio_view_list.html', context)


def ratio_view_detail(request, pk):
    """Show detailed analysis for a specific ratio view."""
    ratio_view = get_object_or_404(RatioView, pk=pk)
    
    days = Day.objects.filter(
        date__range=[ratio_view.start_date, ratio_view.end_date]
    ).prefetch_related('states')
    
    states = State.objects.all()
    state_counts = {}
    for state in states:
        count = days.filter(states=state).count()
        if count > 0:
            state_counts[state] = {
                'count': count,
                'threshold': state.day_threshold,
                'percentage': (count / state.day_threshold * 100) if state.day_threshold > 0 else 0
            }
    
    context = {
        'ratio_view': ratio_view,
        'days': days,
        'state_counts': state_counts,
        'total_days': ratio_view.days_in_range,
        'settings': settings,
    }
    return render(request, 'tracker/ratio_view_detail.html', context)
