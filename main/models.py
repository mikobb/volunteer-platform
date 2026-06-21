from django.db import models
from django.contrib.auth.models import User


class VolunteerProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    full_name = models.CharField(
        max_length=255
    )

    phone = models.CharField(
        max_length=30,
        blank=True
    )

    city = models.CharField(
        max_length=100,
        blank=True
    )

    total_hours = models.PositiveIntegerField(
        default=0
    )

    @property
    def rank(self):
        hours = self.total_hours

        if hours >= 21:
            return "Мастер"
        elif hours >= 17:
            return "Вдохновитель"
        elif hours >= 14:
            return "Амбассадор"
        elif hours >= 11:
            return "Координатор"
        elif hours >= 8:
            return "Опытный"
        elif hours >= 5:
            return "Активист"
        elif hours >= 2:
            return "Участник"
        return "Новичок"

    @property
    def rank_emoji(self):
        if self.total_hours >= 21:
            return "💫"
        elif self.total_hours >= 17:
            return "🌟"
        elif self.total_hours >= 14:
            return "🧭"
        elif self.total_hours >= 11:
            return "🎯"
        elif self.total_hours >= 8:
            return "💡"
        elif self.total_hours >= 5:
            return "🤝"
        elif self.total_hours >= 2:
            return "✨"
        return "🌱"

    @property
    def next_rank(self):
        hours = self.total_hours

        if hours < 2:
            return "✨ Участник"
        elif hours < 5:
            return "🤝 Активист"
        elif hours < 8:
            return "💡 Опытный"
        elif hours < 11:
            return " Координатор"
        elif hours < 14:
            return "🧭 Амбассадор"
        elif hours < 17:
            return "🌟 Вдохновитель"
        elif hours < 21:
            return "💫 Мастер"
        return "Максимум"

    @property
    def next_rank_hours(self):
        hours = self.total_hours

        if hours < 2:
            return 2
        elif hours < 5:
            return 5
        elif hours < 8:
            return 8
        elif hours < 11:
            return 11
        elif hours < 14:
            return 14
        elif hours < 17:
            return 17
        elif hours < 21:
            return 21
        return None

    @property
    def rank_progress(self):
        hours = self.total_hours

        if hours < 2:
            return int(hours / 2 * 100)
        elif hours < 5:
            return int((hours - 2) / 3 * 100)
        elif hours < 8:
            return int((hours - 5) / 3 * 100)
        elif hours < 11:
            return int((hours - 8) / 3 * 100)
        elif hours < 14:
            return int((hours - 11) / 3 * 100)
        elif hours < 17:
            return int((hours - 14) / 3 * 100)
        elif hours < 21:
            return int((hours - 17) / 4 * 100)
        return 100

    def __str__(self):
        return self.full_name

    
import uuid
import random
import string

class Event(models.Model):

    title = models.CharField(max_length=255)
    organization = models.CharField(max_length=255, default='Организация')
    description = models.TextField()
    city = models.CharField(max_length=100)
    date = models.DateField()
    hours = models.PositiveIntegerField(default=1)
    start_time = models.TimeField(blank=True, null=True, verbose_name='Время начала')
    end_date = models.DateField(blank=True, null=True, verbose_name='Дата окончания')
    end_time = models.TimeField(blank=True, null=True, verbose_name='Время окончания')
    max_participants = models.PositiveIntegerField(default=0, verbose_name='Макс. кол-во участников')

    address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Адрес проведения'
    )
    
    employees = models.ManyToManyField(
        'Employee', 
        blank=True,
        related_name='events',
        verbose_name='Ответственные сотрудники'
    )
    
    # 👇 ИСПРАВЛЕННЫЕ ПОЛЯ (добавлено null=True)
    qr_token = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        verbose_name='QR-токен'
    )
    manual_code = models.CharField(
        max_length=8,
        unique=True,
        null=True,
        blank=True,
        verbose_name='Код для ручного ввода'
    )
    is_completed = models.BooleanField(
        default=False,
        verbose_name='Завершено'
    )
    
    def is_actually_completed(self):
        """Проверяет, завершено ли мероприятие фактически (по времени)"""
        return self.get_status() == 'completed'

    def save(self, *args, **kwargs):
        # Автоматически генерируем qr_token и manual_code при создании
        if not self.qr_token:
            self.qr_token = uuid.uuid4().hex
        
        if not self.manual_code:
            # Генерируем 6-значный буквенно-цифровой код
            while True:
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                if not Event.objects.filter(manual_code=code).exists():
                    self.manual_code = code
                    break
        
        super().save(*args, **kwargs)   
    def __str__(self):
        return self.title


    def get_status(self):
        """Возвращает статус мероприятия с учётом времени"""
        now = datetime.now()
        today = date.today()
        
        # Если дата в прошлом - завершено
        if self.date < today:
            return 'completed'
        
        # Если сегодня - проверяем время окончания
        if self.date == today:
            if self.end_time:
                # Если есть время окончания и оно уже прошло
                event_end_datetime = datetime.combine(self.date, self.end_time)
                if now > event_end_datetime:
                    return 'completed'
            # Если время окончания не указано или ещё не наступило
            return 'active'
        
        # Если дата в будущем
        return 'active'
    
    def is_actually_completed(self):
        """Проверяет, завершено ли мероприятие фактически (по времени)"""
        return self.get_status() == 'completed'
    


class Registration(models.Model):

    volunteer = models.ForeignKey(
        VolunteerProfile,
        on_delete=models.CASCADE
    )

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE
    )

    joined_at = models.DateTimeField(
        auto_now_add=True
    )

    checked_in = models.BooleanField(
        default=False
    )

    hours_added = models.BooleanField(
        default=False
    )

    class Meta:
        unique_together = (
            'volunteer',
            'event'
        )

    def __str__(self):
        return f'{self.volunteer} - {self.event}'


from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Registration)
def add_hours_after_checkin(
    sender,
    instance,
    **kwargs
):

    if (
        instance.checked_in
        and not instance.hours_added
    ):

        profile = instance.volunteer

        profile.total_hours += instance.event.hours

        profile.save()

        Registration.objects.filter(
            id=instance.id
        ).update(
            hours_added=True
        )

class OrganizationProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='organization_profile'
    )
    
    name = models.CharField(
        max_length=255,
        verbose_name='Название организации'
    )
    
    email = models.EmailField(
        blank=True,
        verbose_name='Email для связи'
    )
    
    phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name='Телефон'
    )
    
    address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Адрес офиса'
    )
    
    def __str__(self):
        return self.name


class Employee(models.Model):
    organization = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='employees',
        verbose_name='Организация'
    )
    
    first_name = models.CharField(
        max_length=100,
        verbose_name='Имя'
    )
    
    last_name = models.CharField(
        max_length=100,
        verbose_name='Фамилия'
    )
    
    position = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Должность'
    )
    
    phone = models.CharField(
        max_length=30,
        blank=True,
        verbose_name='Телефон'
    )
    
    photo = models.ImageField(
        upload_to='employee_photos/',
        blank=True,
        null=True,
        verbose_name='Фото'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    
    def __str__(self):
        return f'{self.first_name} {self.last_name}'
    
    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'