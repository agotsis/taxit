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


def generate_calendar_month(year, month, start_date=None, end_date=None):
    """Generate calendar data for a single month with day objects."""
    cal = calendar.Calendar(firstweekday=calendar.MONDAY).monthdayscalendar(year, month)
    
    # Query days for this month
    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)
    
    days = Day.objects.filter(
        date__range=[month_start, month_end]
    ).prefetch_related('states', 'office')
    
    days_by_date = {day.date: day for day in days}
    
    month_data = {
        'year': year,
        'month': month,
        'month_name': date(year, month, 1).strftime('%B %Y'),
        'weeks': []
    }
    
    for week in cal:
        week_data = []
        for day_num in week:
            if day_num == 0:
                week_data.append(None)
            else:
                day_date = date(year, month, day_num)
                day_obj = days_by_date.get(day_date)
                in_range = True
                if start_date and end_date:
                    in_range = start_date <= day_date <= end_date
                week_data.append({
                    'date': day_date,
                    'day': day_obj,
                    'in_range': in_range
                })
        month_data['weeks'].append(week_data)
    
    return month_data


def year_view(request, year=None):
    """Display days and state counts for a specific year."""
    if year is None:
        year = datetime.now().year
    
    month = request.GET.get('month')
    if month:
        try:
            month = int(month)
            if month < 1 or month > 12:
                month = datetime.now().month
        except ValueError:
            month = datetime.now().month
    else:
        month = datetime.now().month
    
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
    
    calendar_month = generate_calendar_month(year, month)
    
    # Calculate prev/next month
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
    
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    
    context = {
        'year': year,
        'days': days,
        'state_counts': state_counts,
        'states': states,
        'calendar_month': calendar_month,
        'current_month': month,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'day_types': Day.DayType.choices,
        'offices': Office.objects.all(),
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
    
    month_param = request.GET.get('month')
    year_param = request.GET.get('year')
    
    if month_param and year_param:
        try:
            month = int(month_param)
            year = int(year_param)
            if month < 1 or month > 12:
                month = ratio_view.start_date.month
                year = ratio_view.start_date.year
        except ValueError:
            month = ratio_view.start_date.month
            year = ratio_view.start_date.year
    else:
        month = ratio_view.start_date.month
        year = ratio_view.start_date.year
    
    days = Day.objects.filter(
        date__range=[ratio_view.start_date, ratio_view.end_date]
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
    
    # Generate calendar for current month
    calendar_month = generate_calendar_month(year, month, ratio_view.start_date, ratio_view.end_date)
    
    # Calculate prev/next month within the ratio view range
    current_date = date(year, month, 1)
    
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
    
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    
    # Check if prev/next are within range
    prev_date = date(prev_year, prev_month, 1)
    next_date = date(next_year, next_month, 1)
    
    has_prev = prev_date >= date(ratio_view.start_date.year, ratio_view.start_date.month, 1)
    has_next = next_date <= date(ratio_view.end_date.year, ratio_view.end_date.month, 1)
    
    context = {
        'ratio_view': ratio_view,
        'days': days,
        'state_counts': state_counts,
        'total_days': total_workdays_logged,  # Use actual workdays logged
        'total_workdays_logged': total_workdays_logged,
        'calendar_month': calendar_month,
        'current_month': month,
        'current_year': year,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'has_prev': has_prev,
        'has_next': has_next,
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
