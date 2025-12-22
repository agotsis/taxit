from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Q
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from datetime import datetime, date, timedelta
import calendar
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
    
    # Filter to workdays only (Monday=0 through Friday=4)
    days = Day.objects.filter(
        date__range=[ratio_view.start_date, ratio_view.end_date],
        date__week_day__in=[2, 3, 4, 5, 6]  # Django ORM: 2=Monday ... 6=Friday
    ).prefetch_related('states', 'office')
    
    # Total workdays with any state logged in the period
    total_workdays_logged = days.filter(states__isnull=False).distinct().count()
    
    states = State.objects.all()
    state_counts = {}
    for state in states:
        count = days.filter(states=state).count()
        if count > 0:
            state_counts[state] = {
                'count': count,
                'threshold': state.day_threshold,
                'percentage': (count / state.day_threshold * 100) if state.day_threshold > 0 else 0,
                'ratio': (count / total_workdays_logged * 100) if total_workdays_logged > 0 else 0
            }
    
    # Generate calendar data for each month in the period
    calendar_months = []
    current = date(ratio_view.start_date.year, ratio_view.start_date.month, 1)
    end_month = date(ratio_view.end_date.year, ratio_view.end_date.month, 1)
    
    # Create a lookup dict for days by date
    days_by_date = {day.date: day for day in days}
    
    while current <= end_month:
        cal = calendar.monthcalendar(current.year, current.month)
        month_data = {
            'year': current.year,
            'month': current.month,
            'month_name': current.strftime('%B %Y'),
            'weeks': []
        }
        
        for week in cal:
            week_data = []
            for day_num in week:
                if day_num == 0:
                    week_data.append(None)
                else:
                    day_date = date(current.year, current.month, day_num)
                    day_obj = days_by_date.get(day_date)
                    week_data.append({
                        'date': day_date,
                        'day': day_obj,
                        'in_range': ratio_view.start_date <= day_date <= ratio_view.end_date
                    })
            month_data['weeks'].append(week_data)
        
        calendar_months.append(month_data)
        # Move to next month
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    
    context = {
        'ratio_view': ratio_view,
        'days': days,
        'state_counts': state_counts,
        'total_days': ratio_view.workdays_in_range,
        'total_workdays_logged': total_workdays_logged,
        'calendar_months': calendar_months,
        'day_types': Day.DayType.choices,
        'states': State.objects.all(),
        'offices': Office.objects.all(),
        'settings': settings,
    }
    return render(request, 'tracker/ratio_view_detail.html', context)


def day_json(request, date_str):
    """Return day data as JSON for the modal."""
    try:
        day_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        day = Day.objects.filter(date=day_date).prefetch_related('states', 'office').first()
        
        if day:
            data = {
                'date': date_str,
                'day_type': day.day_type,
                'states': [state.id for state in day.states.all()],
                'office_id': day.office_id if day.office else None,
                'note': day.note,
            }
        else:
            # Return empty data for new day
            data = {
                'date': date_str,
                'day_type': 'WORK',
                'states': [],
                'office_id': None,
                'note': '',
            }
            
        return JsonResponse(data)
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)


@require_http_methods(["POST"])
def day_update(request, date_str):
    """Update day data via POST."""
    try:
        day_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        day, created = Day.objects.get_or_create(date=day_date)
        
        # Update day type
        day.day_type = request.POST.get('day_type', Day.DayType.STANDARD_WORKDAY)
        
        # Update note
        day.note = request.POST.get('note', '')
        
        # Update office
        office_id = request.POST.get('office')
        day.office_id = int(office_id) if office_id and office_id != '' else None
        
        day.save()
        
        # Update states
        state_ids = request.POST.getlist('states')
        day.states.set(state_ids)
        
        return JsonResponse({'success': True})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
