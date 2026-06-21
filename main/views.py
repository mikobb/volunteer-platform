from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login
from django.contrib.auth import authenticate 
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from datetime import date, timedelta, datetime
from django.contrib import messages
from django.http import HttpResponse
import re
import qrcode
from io import BytesIO
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.styles import getSampleStyleSheet
from .models import Employee
from django.core.files.storage import default_storage

from .models import (
    VolunteerProfile,
    Event,
    Registration,
    OrganizationProfile,
)

def get_organization_name(user):
    # Сначала пытаемся получить из БД
    try:
        return user.organization_profile.name
    except OrganizationProfile.DoesNotExist:
        # Если профиля нет — создаём его с названием из словаря
        organizations = {
            'org1': 'Штаб «Вместе»',
            'org2': 'Фонд «СоДействие»',
            'org3': 'Центр Волонтёров'
        }
        name = organizations.get(user.username, 'Организация')
        
        # Создаём профиль автоматически
        OrganizationProfile.objects.create(
            user=user,
            name=name
        )
        return name

def auth_view(request):
    return render(
        request,
        'main/auth.html'
    )


def register_view(request):

    if request.method == 'POST':

        if not request.POST.get('terms'):

            messages.error(
                request,
                'Для продолжения необходимо подтвердить согласие с условиями использования и политикой конфиденциальности'
            )

            return redirect('auth')

        full_name = request.POST.get('full_name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        city = request.POST.get('city')
        password = request.POST.get('password')

        if not re.fullmatch(
            r"[А-Яа-яЁё\-\s]{2,50}",
            city
        ):

            messages.error(
                request,
                'Введите корректное название города'
            )

            return redirect('auth')

        if User.objects.filter(username=username).exists():

            messages.error(
                request,
                'Пользователь с таким логином уже существует'
            )
            return redirect('auth')
        
        if User.objects.filter(email=email).exists():

            messages.error(
                request,
                'Пользователь с таким email уже зарегистрирован'
            )

            return redirect('auth')
        
        if len(password) < 6:

            messages.error(
                request,
                'Пароль должен содержать минимум 6 символов'
            )

            return redirect('auth')
        

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        VolunteerProfile.objects.create(
            user=user,
            full_name=full_name,
            phone=phone,
            city=city
        )

        login(request, user)

        return redirect('volunteer')

    return redirect('auth')


def login_view(request):

    if request.method == 'POST':

        username = request.POST.get('username')
        password = request.POST.get('password')

        role = request.POST.get('role')
        remember_me = request.POST.get('remember_me')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            is_organization = user.username in ['org1', 'org2', 'org3']

            if role == 'organization' and not is_organization:

                messages.error(
                    request,
                    'Этот аккаунт зарегистрирован как волонтёр'
                )

                return redirect('auth')

            if role == 'volunteer' and is_organization:

                messages.error(
                    request,
                    'Для входа используйте вкладку «Организатор»'
                )

                return redirect('auth')

            login(request, user)

            if remember_me:

                request.session.set_expiry(
                    60 * 60 * 24 * 30
                )

            else:

                request.session.set_expiry(0)

            if is_organization:
                return redirect('organization')

            return redirect('volunteer')

        messages.error(
            request,
            'Неверный логин или пароль'
        )

        return redirect('auth')

    return redirect('auth')


from datetime import date

from django.db.models import Count

@login_required
def volunteer_view(request):
    profile = request.user.volunteerprofile
    
    # Все мероприятия (кроме завершённых) с аннотацией количества записанных
    events = Event.objects.filter(
        is_completed=False,
        date__gte=date.today()
    ).annotate(
        registered_count=Count('registration')
    ).order_by('date', 'start_time')

    for event in events:
        event.spots_left = event.max_participants - event.registered_count
    
    # Все регистрации волонтёра
    registrations = Registration.objects.filter(
        volunteer=profile
    ).select_related('event').order_by('-joined_at')
    
    # Активные события (будущие, на которые записан)
    active_events = registrations.filter(
        event__date__gte=date.today(),
        event__is_completed=False
    )
    
    # Сертификаты (отмеченные через QR)
    certificates = registrations.filter(
        checked_in=True,
        event__is_completed=True
    ).select_related('event')
    
    # ID мероприятий, на которые уже записан
    joined_events = list(registrations.values_list('event_id', flat=True))
    
    # Статистика
    completed_count = registrations.filter(
        event__is_completed=True,
        checked_in=True
    ).count()
    
    return render(request, 'main/volunteer.html', {
        'profile': profile,
        'events': events,
        'registrations': registrations,
        'active_events': active_events,
        'certificates': certificates,
        'joined_events': joined_events,
        'completed_count': completed_count,
        'today': date.today(),
    })


from datetime import date, datetime, timedelta

@login_required
def organization_view(request):
    organization_name = get_organization_name(request.user)
    org_image = get_organization_image(request.user)
    
    # Получаем профиль организации
    org_profile, created = OrganizationProfile.objects.get_or_create(
        user=request.user,
        defaults={'name': organization_name}
    )
    
    all_events = Event.objects.filter(
        organization=organization_name
    ).order_by('date', 'start_time')
    
    now = datetime.now()
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    qr_events = []
    for event in all_events:
        if event.date == today:
            if event.start_time:
                event_datetime = datetime.combine(event.date, event.start_time)
                if event_datetime >= now - timedelta(hours=24):
                    qr_events.append(event)
            else:
                qr_events.append(event)
        elif event.date == tomorrow:
            if event.start_time:
                event_datetime = datetime.combine(event.date, event.start_time)
                if event_datetime <= now + timedelta(hours=24):
                    qr_events.append(event)
            else:
                qr_events.append(event)
    
    registrations = Registration.objects.filter(
        event__organization=organization_name
    ).select_related(
        'volunteer',
        'volunteer__user',
        'event'
    ).order_by('-joined_at')
    
    certificates = Registration.objects.filter(
        event__organization=organization_name,
        checked_in=True
    ).select_related(
        'volunteer',
        'event'
    ).order_by('-joined_at')
    
    return render(
        request,
        'main/organization.html',
        {
            'organization_name': organization_name,
            'org_image': org_image,
            'org_profile': org_profile,  # 👈 Передаём профиль
            'events': all_events,
            'qr_events': qr_events,
            'registrations': registrations,
            'certificates': certificates,
            'today': today,
        }
    )

@login_required
def save_organization_profile_view(request):
    if request.method == 'POST':
        org_profile, created = OrganizationProfile.objects.get_or_create(
            user=request.user
        )
        
        # Получаем данные из формы
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        current_password = request.POST.get('current_password', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        
        # Валидация названия
        if not name:
            messages.error(request, 'Название организации не может быть пустым')
            return redirect('organization')
        
        # Обновляем данные профиля
        org_profile.name = name
        org_profile.email = email
        org_profile.phone = phone
        org_profile.address = address
        org_profile.save()
        
        # Также обновляем название в мероприятиях, если оно изменилось
        old_name = get_organization_name(request.user)
        if old_name != name:
            Event.objects.filter(organization=old_name).update(organization=name)
        
        # Обработка смены пароля
        if current_password and new_password:
            if not request.user.check_password(current_password):
                messages.error(request, 'Текущий пароль введён неверно')
                return redirect('organization')
            
            if len(new_password) < 3:
                messages.error(request, 'Новый пароль должен содержать минимум 3 символов')
                return redirect('organization')
            
            request.user.set_password(new_password)
            request.user.save()
            messages.success(request, 'Пароль успешно изменён. Пожалуйста, войдите снова.')
            return redirect('auth')
        
        messages.success(request, 'Профиль организации успешно обновлён!')
        return redirect('organization')
    
    return redirect('organization')


def get_organization_image(user):
    """Возвращает путь к изображению организации"""
    org_images = {
        'org1': 'images/organizations/org1.png',
        'org2': 'images/organizations/org2.png',
        'org3': 'images/organizations/org3.png',
    }
    return org_images.get(user.username, 'images/organizations/org1.png')


@login_required
def organization_certificate_view(request, registration_id):
    """Организация может скачать сертификат волонтёра за своё мероприятие"""
    organization_name = get_organization_name(request.user)
    
    registration = get_object_or_404(
        Registration,
        id=registration_id,
        event__organization=organization_name,
        checked_in=True
    )
    
    response = HttpResponse(
        content_type='application/pdf'
    )
    response['Content-Disposition'] = (
        f'attachment; filename="certificate_{registration.id}.pdf"'
    )
    
    doc = SimpleDocTemplate(response)
    
    pdfmetrics.registerFont(
        TTFont(
            'Arial',
            r'C:\Windows\Fonts\arial.ttf'
        )
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        fontName='Arial',
        alignment=TA_CENTER,
        fontSize=28,
        spaceAfter=30
    )
    
    name_style = ParagraphStyle(
        'NameStyle',
        parent=styles['Heading1'],
        fontName='Arial',
        alignment=TA_CENTER,
        fontSize=24,
        textColor=colors.darkblue,
        spaceAfter=25
    )
    
    center_style = ParagraphStyle(
        'CenterStyle',
        parent=styles['BodyText'],
        fontName='Arial',
        alignment=TA_CENTER,
        fontSize=14,
        leading=24
    )
    
    content = [
        Spacer(1, 40),
        Paragraph("СЕРТИФИКАТ", title_style),
        Spacer(1, 20),
        Paragraph("Настоящим подтверждается, что", center_style),
        Spacer(1, 15),
        Paragraph(registration.volunteer.full_name, name_style),
        Paragraph("принял(а) участие в волонтёрском мероприятии", center_style),
        Spacer(1, 15),
        Paragraph(f"<b>«{registration.event.title}»</b>", center_style),
        Spacer(1, 20),
        Paragraph(f"Подтверждено часов: <b>{registration.event.hours}</b>", center_style),
        Spacer(1, 10),
        Paragraph(f"Дата проведения: <b>{registration.event.date}</b>", center_style),
        Spacer(1, 10),
        Paragraph(f"Организатор: <b>{registration.event.organization}</b>", center_style),
        Spacer(1, 50),
        Paragraph("Благодарим за вклад в развитие добровольческого движения!", center_style),
    ]
    
    doc.build(content)
    
    return response



@login_required
def create_event_view(request):
    if request.method == 'POST':
        organization_name = get_organization_name(request.user)
        
        title = request.POST.get('title')
        description = request.POST.get('description')
        city = request.POST.get('city')
        address=request.POST.get('address')
        date_str = request.POST.get('date')
        start_time_str = request.POST.get('start_time')
        end_date_str = request.POST.get('end_date')
        end_time_str = request.POST.get('end_time')
        hours = int(request.POST.get('hours', 1))
        max_participants = int(request.POST.get('max_participants', 0))
        
        # 🔍 ВАЛИДАЦИЯ
        if date_str and end_date_str:
            start_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            if end_date < start_date:
                return JsonResponse({
                    'success': False,
                    'message': 'Дата окончания не может быть раньше даты начала'
                })
            
            if start_date == end_date and start_time_str and end_time_str:
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                end_time = datetime.strptime(end_time_str, '%H:%M').time()
                
                if end_time <= start_time:
                    return JsonResponse({
                        'success': False,
                        'message': 'Время окончания должно быть позже времени начала'
                    })

        event = Event.objects.create(
            title=title,
            description=description,
            city=city,
            date=date_str or None,
            hours=hours,
            start_time=start_time_str or None,
            end_date=end_date_str or None,
            end_time=end_time_str or None,
            max_participants=max_participants,
            organization=organization_name,
        )
        
        #  добавляем выбранных сотрудников
        employee_ids = request.POST.getlist('employee_ids')
        if employee_ids:
            employees = Employee.objects.filter(
                id__in=employee_ids,
                organization=request.user
            )
            event.employees.set(employees)
        
        return JsonResponse({
            'success': True,
            'message': 'Мероприятие успешно создано!'
        })
    
    return JsonResponse({'success': False, 'message': 'Неверный запрос'})


@login_required
def edit_event_view(request, event_id):
    organization_name = get_organization_name(request.user)
    event = get_object_or_404(Event, id=event_id, organization=organization_name)
    
    if request.method == 'POST':
        date_str = request.POST.get('date')
        start_time_str = request.POST.get('start_time')
        end_date_str = request.POST.get('end_date')
        end_time_str = request.POST.get('end_time')
        
        # 🔍 ВАЛИДАЦИЯ
        if date_str and end_date_str:
            start_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            if end_date < start_date:
                return JsonResponse({
                    'success': False,
                    'message': 'Дата окончания не может быть раньше даты начала'
                })
            
            if start_date == end_date and start_time_str and end_time_str:
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
                end_time = datetime.strptime(end_time_str, '%H:%M').time()
                
                if end_time <= start_time:
                    return JsonResponse({
                        'success': False,
                        'message': 'Время окончания должно быть позже времени начала'
                    })
        
        event.title = request.POST.get('title')
        event.description = request.POST.get('description')
        event.city = request.POST.get('city')
        event.address = request.POST.get('address')
        event.date = date_str or event.date
        event.hours = int(request.POST.get('hours', event.hours))
        event.start_time = start_time_str or None
        event.end_date = end_date_str or None
        event.end_time = end_time_str or None
        event.max_participants = int(request.POST.get('max_participants', 0))
        event.save()

        employee_ids = request.POST.getlist('employee_ids')
        if employee_ids:
            employees = Employee.objects.filter(
                id__in=employee_ids,
                organization=request.user
            )
            event.employees.set(employees)
        else:
            event.employees.clear()
        
        return JsonResponse({
            'success': True,
            'message': 'Изменения сохранены!'
        })
    
    return JsonResponse({'success': False, 'message': 'Неверный запрос'})

@login_required
def delete_event_view(request, event_id):
    organization_name = get_organization_name(request.user)
    
    # Находим событие и проверяем, что оно принадлежит этой организации
    event = get_object_or_404(
        Event,
        id=event_id,
        organization=organization_name
    )
    
    if request.method == 'POST':
        event_title = event.title
        event.delete()  # Каскадно удалятся и все связанные Registration
        return JsonResponse({
            'success': True,
            'message': f'Мероприятие «{event_title}» удалено'
        })
    
    return JsonResponse({
        'success': False,
        'message': 'Неверный запрос'
    })

# ========== QR-КОДЫ ==========

@login_required
def generate_qr_view(request, event_id):
    """Генерация QR-кода для мероприятия (возвращает PNG-изображение)"""
    organization_name = get_organization_name(request.user)
    event = get_object_or_404(
        Event,
        id=event_id,
        organization=organization_name
    )
    
    # Убираем префикс, оставляем только токен
    qr_data = event.qr_token  # <-- Было: f"CHECKIN:{event.qr_token}"
    
    # Генерируем QR-код
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # <-- Увеличил надёжность
        box_size=15,  # <-- Увеличил размер для лучшего сканирования
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Возвращаем как PNG
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return HttpResponse(buffer.getvalue(), content_type='image/png')


@login_required
def get_event_qr_info(request, event_id):
    """Возвращает информацию о мероприятии для раздела QR (AJAX)"""
    organization_name = get_organization_name(request.user)
    event = get_object_or_404(
        Event,
        id=event_id,
        organization=organization_name
    )
    
    registrations = Registration.objects.filter(event=event)    
    checked_in_count = registrations.filter(checked_in=True).count()
    total_count = registrations.count()
    
    # Формируем время активности
    time_str = ''
    if event.start_time:
        time_str += f'с {event.start_time.strftime("%H:%M")}'
    if event.end_time:
        time_str += f' до {event.end_time.strftime("%H:%M")}'
    if not time_str:
        time_str = 'Весь день'
    
    return JsonResponse({
        'success': True,
        'event': {
            'id': event.id,
            'title': event.title,
            'date': event.date.strftime('%d.%m.%Y'),
            'time': time_str,
            'manual_code': event.manual_code,
            'is_completed': event.is_completed,
            'checked_in': checked_in_count,
            'total': total_count,
            'qr_url': f'/qr-image/{event.id}/',
        }
    })


@login_required
def complete_event_view(request, event_id):
    """Завершение мероприятия — начисление часов всем, кто отметился"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Неверный запрос'})
    
    organization_name = get_organization_name(request.user)
    event = get_object_or_404(
        Event,
        id=event_id,
        organization=organization_name
    )
    
    if event.is_completed:
        return JsonResponse({
            'success': False,
            'message': 'Мероприятие уже завершено'
        })
    
    # Отмечаем всех зарегистрированных как checked_in
    # (Те, кто уже checked_in, не изменятся. Те, кто не отмечался — тоже не получат часы)
    checked_registrations = Registration.objects.filter(
        event=event,
        checked_in=True,
        hours_added=False
    )
    
    hours_given = 0
    for reg in checked_registrations:
        reg.volunteer.total_hours += event.hours
        reg.volunteer.save()
        reg.hours_added = True
        reg.save()
        hours_given += 1
    
    event.is_completed = True
    event.save()
    
    return JsonResponse({
        'success': True,
        'message': f'Мероприятие завершено! Часы начислены {hours_given} волонтёрам.',
        'hours_given': hours_given,
    })


@login_required
def save_profile_view(request):

    if request.method == 'POST':

        profile = request.user.volunteerprofile

        request.user.username = request.POST.get('username')
        request.user.email = request.POST.get('email')

        profile.phone = request.POST.get('phone')
        profile.city = request.POST.get('city')

        request.user.save()
        profile.save()

    return redirect('volunteer')

def logout_view(request):

    logout(request)

    return redirect('auth')


@login_required
def join_event(request, event_id):
    profile = request.user.volunteerprofile
    event = get_object_or_404(Event, id=event_id)
    
    # 🔍 ПРОВЕРКА: есть ли места
    if event.max_participants > 0:
        registered_count = Registration.objects.filter(event=event).count()
        
        if registered_count >= event.max_participants:
            messages.error(
                request,
                'К сожалению, все места на это мероприятие уже заняты'
            )
            return redirect('volunteer')
    
    # Создаём регистрацию
    Registration.objects.get_or_create(
        volunteer=profile,
        event=event
    )
    
    messages.success(
        request,
        f'Вы успешно записались на мероприятие «{event.title}»!'
    )
    return redirect('volunteer')


@login_required
def certificate_view(request, registration_id):

    registration = Registration.objects.get(
        id=registration_id,
        volunteer=request.user.volunteerprofile
    )

    response = HttpResponse(
        content_type='application/pdf'
    )

    response['Content-Disposition'] = (
        f'attachment; filename="certificate_{registration.id}.pdf"'
    )

    doc = SimpleDocTemplate(response)

    pdfmetrics.registerFont(
        TTFont(
            'Arial',
            r'C:\Windows\Fonts\arial.ttf'
        )
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Title'],
        fontName='Arial',
        alignment=TA_CENTER,
        fontSize=28,
        spaceAfter=30
    )

    name_style = ParagraphStyle(
        'NameStyle',
        parent=styles['Heading1'],
        fontName='Arial',
        alignment=TA_CENTER,
        fontSize=24,
        textColor=colors.darkblue,
        spaceAfter=25
    )

    center_style = ParagraphStyle(
        'CenterStyle',
        parent=styles['BodyText'],
        fontName='Arial',
        alignment=TA_CENTER,
        fontSize=14,
        leading=24
    )

    content = [

        Spacer(1, 40),

        Paragraph(
            "СЕРТИФИКАТ",
            title_style
        ),

        Spacer(1, 20),

        Paragraph(
            "Настоящим подтверждается, что",
            center_style
        ),

        Spacer(1, 15),

        Paragraph(
            registration.volunteer.full_name,
            name_style
        ),

        Paragraph(
            "принял(а) участие в волонтёрском мероприятии",
            center_style
        ),

        Spacer(1, 15),

        Paragraph(
            f"<b>«{registration.event.title}»</b>",
            center_style
        ),

        Spacer(1, 20),

        Paragraph(
            f"Подтверждено часов: <b>{registration.event.hours}</b>",
            center_style
        ),

        Spacer(1, 10),

        Paragraph(
            f"Дата проведения: <b>{registration.event.date}</b>",
            center_style
        ),

        Spacer(1, 50),

        Paragraph(
            "Благодарим за вклад в развитие добровольческого движения!",
            center_style
        ),
    ]

    doc.build(content)

    return response

@login_required
def cancel_registration(
    request,
    registration_id
):

    registration = Registration.objects.get(
        id=registration_id,
        volunteer=request.user.volunteerprofile
    )

    registration.delete()

    return redirect('volunteer')


def terms_view(request):

    return render(
        request,
        'main/terms.html'
    )


def privacy_view(request):

    return render(
        request,
        'main/privacy.html'
    )

@login_required
def add_employee_view(request):
    """Добавление сотрудника"""
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        position = request.POST.get('position', '').strip()
        phone = request.POST.get('phone', '').strip()
        photo = request.FILES.get('photo')
        
        if not first_name or not last_name:
            return JsonResponse({
                'success': False,
                'message': 'Имя и фамилия обязательны'
            })
        
        employee = Employee.objects.create(
            organization=request.user,
            first_name=first_name,
            last_name=last_name,
            position=position,
            phone=phone,
            photo=photo if photo else None
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Сотрудник добавлен',
            'employee': {
                'id': employee.id,
                'first_name': employee.first_name,
                'last_name': employee.last_name,
                'position': employee.position,
                'phone': employee.phone,
                'photo_url': employee.photo.url if employee.photo else ''
            }
        })
    
    return JsonResponse({'success': False, 'message': 'Неверный запрос'})


@login_required
def delete_employee_view(request, employee_id):
    """Удаление сотрудника"""
    if request.method == 'POST':
        employee = get_object_or_404(
            Employee,
            id=employee_id,
            organization=request.user
        )
        
        # Удаляем фото, если есть
        if employee.photo:
            employee.photo.delete(save=False)
        
        employee.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'Сотрудник удалён'
        })
    
    return JsonResponse({'success': False, 'message': 'Неверный запрос'})


@login_required
def get_employees_view(request):
    """Получение списка сотрудников организации (для AJAX)"""
    employees = Employee.objects.filter(
        organization=request.user
    ).order_by('last_name', 'first_name')
    
    employees_data = []
    for emp in employees:
        employees_data.append({
            'id': emp.id,
            'first_name': emp.first_name,
            'last_name': emp.last_name,
            'position': emp.position,
            'phone': emp.phone,
            'photo_url': emp.photo.url if emp.photo else ''
        })
    
    return JsonResponse({
        'success': True,
        'employees': employees_data
    })


@login_required
def event_employees_view(request, event_id):
    """Получение сотрудников, ответственных за событие"""
    event = get_object_or_404(Event, id=event_id)
    
    employees = event.employees.all().order_by('last_name', 'first_name')
    
    employees_data = []
    for emp in employees:
        employees_data.append({
            'id': emp.id,
            'first_name': emp.first_name,
            'last_name': emp.last_name,
            'position': emp.position,
            'phone': emp.phone,
            'photo_url': emp.photo.url if emp.photo else ''
        })
    
    return JsonResponse({
        'success': True,
        'employees': employees_data
    })


from django.views.decorators.http import require_POST

@login_required
@require_POST
def checkin_qr_view(request):
    """Отметка присутствия через QR-код"""
    qr_token = request.POST.get('qr_token')
    
    if not qr_token:
        return JsonResponse({
            'success': False,
            'message': 'QR-код не указан'
        })
    
    # Находим мероприятие по токену
    try:
        event = Event.objects.get(qr_token=qr_token)
    except Event.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Недействительный QR-код'
        })
    
    # Проверяем, что мероприятие не завершено
    if event.is_completed:
        return JsonResponse({
            'success': False,
            'message': 'Мероприятие уже завершено'
        })
    
    # Проверяем, что волонтёр записан на мероприятие
    try:
        registration = Registration.objects.get(
            volunteer=request.user.volunteerprofile,
            event=event
        )
    except Registration.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Вы не записаны на это мероприятие'
        })
    
    # Проверяем, что уже не отмечен
    if registration.checked_in:
        return JsonResponse({
            'success': False,
            'message': 'Вы уже отметили присутствие'
        })
    
    # Отмечаем присутствие
    registration.checked_in = True
    registration.save()
    
    return JsonResponse({
        'success': True,
        'message': f'Присутствие отмечено! Мероприятие: {event.title}'
    })


@login_required
@require_POST
def checkin_manual_view(request):
    """Отметка присутствия через ручной ввод кода"""
    manual_code = request.POST.get('manual_code', '').strip().upper()
    
    if not manual_code:
        return JsonResponse({
            'success': False,
            'message': 'Код не указан'
        })
    
    # Находим мероприятие по коду
    try:
        event = Event.objects.get(manual_code=manual_code)
    except Event.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Недействительный код'
        })
    
    # Проверяем, что мероприятие не завершено
    if event.is_completed:
        return JsonResponse({
            'success': False,
            'message': 'Мероприятие уже завершено'
        })
    
    # Проверяем, что волонтёр записан
    try:
        registration = Registration.objects.get(
            volunteer=request.user.volunteerprofile,
            event=event
        )
    except Registration.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Вы не записаны на это мероприятие'
        })
    
    # Проверяем, что уже не отмечен
    if registration.checked_in:
        return JsonResponse({
            'success': False,
            'message': 'Вы уже отметили присутствие'
        })
    
    # Отмечаем присутствие
    registration.checked_in = True
    registration.save()
    
    return JsonResponse({
        'success': True,
        'message': f'Присутствие отмечено! Мероприятие: {event.title}'
    })


@login_required
def event_employees_for_volunteer(request, event_id):
    """Получение сотрудников для волонтера"""
    event = get_object_or_404(Event, id=event_id)
    
    employees = event.employees.all().order_by('last_name', 'first_name')
    
    employees_data = []
    for emp in employees:
        employees_data.append({
            'id': emp.id,
            'first_name': emp.first_name,
            'last_name': emp.last_name,
            'position': emp.position,
            'phone': emp.phone
        })
    
    return JsonResponse({
        'success': True,
        'employees': employees_data
    })