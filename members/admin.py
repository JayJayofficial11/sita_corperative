from django.contrib import admin
from .models import Member, MembershipType

class MemberAdmin(admin.ModelAdmin):
    list_display = ('member_id', 'full_name', 'user__email', 'membership_status', 'date_joined', 'registration_fee_paid')
    list_filter = ('membership_status', 'gender', 'marital_status', 'registration_fee_paid', 'date_joined')
    search_fields = ('member_id', 'user__username', 'user__first_name', 'user__last_name', 'user__email')
    readonly_fields = ('member_id', 'created_at', 'updated_at', 'age')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'member_id')
        }),
        ('Personal Information', {
            'fields': ('date_of_birth', 'gender', 'marital_status', 'occupation', 'employer', 'monthly_savings')
        }),
        ('Contact Information', {
            'fields': ('address', 'city', 'state', 'postal_code', 'emergency_contact_name', 'emergency_contact_phone')
        }),
        ('Membership Information', {
            'fields': ('membership_status', 'date_joined', 'registration_fee_paid', 'registration_fee_amount')
        }),
        ('Guarantor Information', {
            'fields': ('guarantor_name', 'guarantor_phone', 'guarantor_address')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def full_name(self, obj):
        return obj.user.get_full_name()
    full_name.short_description = 'Full Name'
    
    def user__email(self, obj):
        return obj.user.email
    user__email.short_description = 'Email'

class MembershipTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'registration_fee', 'monthly_contribution', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')

admin.site.register(Member, MemberAdmin)
admin.site.register(MembershipType, MembershipTypeAdmin)
