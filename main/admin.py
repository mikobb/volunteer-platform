from django.contrib import admin


from .models import (
    VolunteerProfile,
    Event,
    Registration
)

admin.site.register(VolunteerProfile)
admin.site.register(Event)
admin.site.register(Registration)