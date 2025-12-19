from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Submit, HTML
from crispy_forms.bootstrap import FormActions
from .models import Member, MembershipType

User = get_user_model()

class UserRegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'phone_number', 'profile_picture']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., +1234567890 or 1234567890',
                'pattern': r'^\+?1?\d{9,15}$',
            }),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }
        help_texts = {
            'phone_number': 'Enter phone number with optional country code (e.g., +1234567890 or 1234567890)',
            'username': 'Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.',
        }

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match")
        return password2

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email address is already registered.")
        return email
    
    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone:
            # Remove spaces and common formatting characters
            phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            # Add + if it starts with a digit and is long enough
            if phone.isdigit() and len(phone) >= 10:
                if not phone.startswith('+'):
                    phone = '+' + phone
            self.cleaned_data['phone_number'] = phone
        return phone

class MemberRegistrationForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = [
            'date_of_birth', 'gender', 'marital_status', 'address', 'city', 'state',
            'postal_code', 'emergency_contact_name', 'emergency_contact_phone',
            'occupation', 'employer', 'monthly_savings', 'entrance_date', 'guarantor_name',
            'guarantor_phone', 'guarantor_address', 'registration_fee_amount'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'marital_status': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'employer': forms.TextInput(attrs={'class': 'form-control'}),
            'monthly_savings': forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01', 'min': '1'}),
            'entrance_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'guarantor_name': forms.TextInput(attrs={'class': 'form-control'}),
            'guarantor_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'guarantor_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'registration_fee_amount': forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset(
                'Personal Information',
                Row(
                    Column('date_of_birth', css_class='col-md-4'),
                    Column('gender', css_class='col-md-4'),
                    Column('marital_status', css_class='col-md-4'),
                ),
                'occupation',
                Row(
                    Column('employer', css_class='col-md-6'),
                    Column('monthly_savings', css_class='col-md-6'),
                )
            ),
            Fieldset(
                'Contact Information',
                'address',
                Row(
                    Column('city', css_class='col-md-4'),
                    Column('state', css_class='col-md-4'),
                    Column('postal_code', css_class='col-md-4'),
                ),
                Row(
                    Column('emergency_contact_name', css_class='col-md-6'),
                    Column('emergency_contact_phone', css_class='col-md-6'),
                )
            ),
            Fieldset(
                'Guarantor Information',
                'guarantor_name',
                Row(
                    Column('guarantor_phone', css_class='col-md-6'),
                    Column('registration_fee_amount', css_class='col-md-6'),
                ),
                'guarantor_address'
            ),
            FormActions(
                Submit('submit', 'Register Member', css_class='btn btn-primary btn-lg'),
                HTML('<a href="{% url \'members:list\' %}" class="btn btn-secondary btn-lg ms-2">Cancel</a>')
            )
        )

    def clean_monthly_savings(self):
        monthly_savings = self.cleaned_data.get('monthly_savings')
        if monthly_savings is not None and monthly_savings <= 0:
            raise ValidationError("Monthly savings must be greater than 0.")
        return monthly_savings

class MemberEditForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = [
            'date_of_birth', 'gender', 'marital_status', 'address', 'city', 'state',
            'postal_code', 'emergency_contact_name', 'emergency_contact_phone',
            'occupation', 'employer', 'monthly_savings', 'entrance_date', 'membership_status',
            'guarantor_name', 'guarantor_phone', 'guarantor_address'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'marital_status': forms.Select(attrs={'class': 'form-select'}),
            'membership_status': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'employer': forms.TextInput(attrs={'class': 'form-control'}),
            'monthly_savings': forms.NumberInput(attrs={'class': 'form-control currency-input', 'step': '0.01', 'min': '1'}),
            'entrance_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'guarantor_name': forms.TextInput(attrs={'class': 'form-control'}),
            'guarantor_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'guarantor_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'phone_number', 'profile_picture', 'role', 'is_verified']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'is_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class MemberSearchForm(forms.Form):
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, member ID, or email...'
        })
    )
    status = forms.ChoiceField(
        choices=[('', 'All Status')] + Member.MEMBERSHIP_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    gender = forms.ChoiceField(
        choices=[('', 'All Genders')] + Member.GENDER_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_joined_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    date_joined_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
