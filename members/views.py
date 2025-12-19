from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from .models import Member, MembershipType
from decimal import Decimal

@login_required
def member_list(request):
    """List all members with search and filtering"""
    from .forms import MemberSearchForm
    from django.core.paginator import Paginator
    from django.db.models import Q, Count
    from datetime import datetime, timedelta
    
    # Get all regular members (exclude admin/staff users)
    members = Member.regular_members().select_related('user')
    
    # Handle search
    search_form = MemberSearchForm(request.GET)
    if search_form.is_valid():
        if search_form.cleaned_data['search']:
            search_term = search_form.cleaned_data['search']
            members = members.filter(
                Q(user__first_name__icontains=search_term) |
                Q(user__last_name__icontains=search_term) |
                Q(user__email__icontains=search_term) |
                Q(member_id__icontains=search_term)
            )
        
        if search_form.cleaned_data['status']:
            members = members.filter(membership_status=search_form.cleaned_data['status'])
        
        if search_form.cleaned_data['gender']:
            members = members.filter(gender=search_form.cleaned_data['gender'])
        
        if search_form.cleaned_data['date_joined_from']:
            members = members.filter(created_at__gte=search_form.cleaned_data['date_joined_from'])
        
        if search_form.cleaned_data['date_joined_to']:
            members = members.filter(created_at__lte=search_form.cleaned_data['date_joined_to'])
    
    # Order members
    members = members.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(members, 20)  # Show 20 members per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate statistics
    total_members = Member.objects.count()
    active_members_count = Member.objects.filter(membership_status='active').count()
    pending_members_count = Member.objects.filter(membership_status='pending').count()
    
    # Members joined this month
    current_month = datetime.now().replace(day=1)
    new_this_month = Member.objects.filter(created_at__gte=current_month).count()
    
    context = {
        'members': page_obj,
        'search_form': search_form,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
        'active_members_count': active_members_count,
        'pending_members_count': pending_members_count,
        'new_this_month': new_this_month,
    }
    return render(request, 'members/list.html', context)

@login_required
def member_register(request):
    """Register new member - bulletproof version"""
    from .forms import UserRegistrationForm, MemberRegistrationForm
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.http import HttpResponse
    
    User = get_user_model()
    
    # Always start with fresh forms
    user_form = UserRegistrationForm()
    member_form = MemberRegistrationForm()
    
    if request.method == 'POST':
        print("\n=== REGISTRATION ATTEMPT ===")
        print(f"POST data: {dict(request.POST)}")
        
        try:
            # Create forms with POST data
            user_form = UserRegistrationForm(request.POST, request.FILES)
            member_form = MemberRegistrationForm(request.POST)
            
            print("Forms created successfully")
            
            # Validate both forms
            user_valid = user_form.is_valid()
            member_valid = member_form.is_valid()
            
            print(f"User form valid: {user_valid}")
            print(f"Member form valid: {member_valid}")
            
            if not user_valid:
                print(f"User form errors: {user_form.errors}")
                messages.error(request, f"User form errors: {user_form.errors}")
                        
            if not member_valid:
                print(f"Member form errors: {member_form.errors}")
                messages.error(request, f"Member form errors: {member_form.errors}")
            
            if user_valid and member_valid:
                print("Both forms valid - creating user and member...")
                
                try:
                    with transaction.atomic():
                        # Create user account
                        user = user_form.save(commit=False)
                        user.set_password(user_form.cleaned_data['password1'])
                        user.role = 'member'
                        user.save()
                        
                        print(f"User created: {user.username} (ID: {user.id})")
                        
                        # Create member profile
                        member = member_form.save(commit=False)
                        member.user = user
                        member.save()
                        
                        print(f"Member created: {member.member_id} (ID: {member.id})")
                        
                        # Success - redirect with message
                        messages.success(
                            request, 
                            f'🎉 SUCCESS! Member {user.get_full_name()} registered with ID: {member.member_id}'
                        )
                        print("=== REGISTRATION SUCCESSFUL ===")
                        return redirect('members:list')
                        
                except Exception as e:
                    print(f"Database error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    messages.error(request, f'Database error: {str(e)}')
            else:
                print("Form validation failed")
                if not user_valid and not member_valid:
                    messages.error(request, 'Both user and member forms have errors. Please check all fields.')
                elif not user_valid:
                    messages.error(request, 'User account form has errors. Please check the account details.')
                else:
                    messages.error(request, 'Member information form has errors. Please check personal details.')
                
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            import traceback
            traceback.print_exc()
            messages.error(request, f'Unexpected error: {str(e)}')
    else:
        print("GET request - showing registration form")
    
    print(f"Rendering template with forms...")
    
    context = {
        'user_form': user_form,
        'member_form': member_form
    }
    return render(request, 'members/register.html', context)

@login_required
def member_register_simple(request):
    """Simple member registration without multi-step wizard"""
    from .forms import UserRegistrationForm, MemberRegistrationForm
    from django.contrib.auth import get_user_model
    from django.db import transaction
    import logging
    
    logger = logging.getLogger(__name__)
    User = get_user_model()
    
    if request.method == 'POST':
        logger.info(f"POST data received: {request.POST}")
        
        # Get form data from POST request
        user_form = UserRegistrationForm(request.POST, request.FILES)
        member_form = MemberRegistrationForm(request.POST)
        
        # Validate both forms
        user_valid = user_form.is_valid()
        member_valid = member_form.is_valid()
        
        logger.info(f"User form valid: {user_valid}")
        logger.info(f"Member form valid: {member_valid}")
        
        if not user_valid:
            logger.error(f"User form errors: {user_form.errors}")
        if not member_valid:
            logger.error(f"Member form errors: {member_form.errors}")
        
        if user_valid and member_valid:
            try:
                with transaction.atomic():
                    # Create user account
                    user = user_form.save(commit=False)
                    user.set_password(user_form.cleaned_data['password1'])
                    user.role = 'member'
                    user.save()
                    
                    logger.info(f"User created: {user.username}")
                    
                    # Create member profile
                    member = member_form.save(commit=False)
                    member.user = user
                    member.save()
                    
                    logger.info(f"Member created: {member.member_id}")
                    
                    messages.success(
                        request, 
                        f'Member {user.get_full_name()} has been successfully registered with ID: {member.member_id}'
                    )
                    return redirect('members:detail', pk=member.pk)
                    
            except Exception as e:
                logger.error(f"Registration exception: {str(e)}")
                messages.error(request, f'Registration failed: {str(e)}')
    else:
        # Initialize empty forms
        user_form = UserRegistrationForm()
        member_form = MemberRegistrationForm()
    
    context = {
        'user_form': user_form,
        'member_form': member_form
    }
    return render(request, 'members/register_simple.html', context)

@login_required
def member_reports(request):
    """Member reports"""
    return render(request, 'members/reports.html')

@login_required
def member_detail(request, pk):
    """Member detail view with financial summary"""
    from savings.models import SavingsAccount, SavingsTransaction
    from loans.models import Loan
    from django.db.models import Sum
    
    member = get_object_or_404(Member, pk=pk)
    
    # Get savings information
    try:
        savings_account = SavingsAccount.objects.get(member=member)
        savings_balance = savings_account.balance
        available_balance = savings_account.available_balance
        collateral_amount = savings_account.collateral_amount
        has_active_loan = savings_account.has_active_loan
        savings_transactions = SavingsTransaction.objects.filter(
            savings_account=savings_account
        ).order_by('-created_at')[:10]  # Last 10 transactions
    except SavingsAccount.DoesNotExist:
        savings_balance = 0
        available_balance = 0
        collateral_amount = 0
        has_active_loan = False
        savings_transactions = []
    
    # Get loan information
    member_loans = Loan.objects.filter(member=member).order_by('-created_at')
    active_loans = member_loans.filter(status='active')
    loan_balance = active_loans.aggregate(
        total=Sum('total_balance')
    )['total'] or 0
    
    # Get loan repayment information
    loan_repayments = []
    if active_loans.exists():
        from savings.models import SavingsTransaction
        loan_repayments = SavingsTransaction.objects.filter(
            savings_account=savings_account,
            is_loan_repayment=True,
            related_loan__in=active_loans
        ).order_by('-created_at')[:5]
    
    # Get recent transactions (placeholder - you might want to create a unified transaction model)
    recent_transactions = []
    
    # Share capital (placeholder - implement if you have share capital model)
    share_capital = 0
    
    context = {
        'member': member,
        'savings_balance': savings_balance,
        'available_balance': available_balance,
        'collateral_amount': collateral_amount,
        'has_active_loan': has_active_loan,
        'savings_transactions': savings_transactions,
        'member_loans': member_loans,
        'active_loans': active_loans,
        'loan_balance': loan_balance,
        'loan_repayments': loan_repayments,
        'share_capital': share_capital,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'members/detail.html', context)

@login_required
def member_edit(request, pk):
    """Edit member information"""
    from .forms import MemberEditForm, UserEditForm
    from django.db import transaction
    
    member = get_object_or_404(Member, pk=pk)
    
    if request.method == 'POST':
        user_form = UserEditForm(request.POST, request.FILES, instance=member.user)
        member_form = MemberEditForm(request.POST, instance=member)
        
        if user_form.is_valid() and member_form.is_valid():
            try:
                with transaction.atomic():
                    user_form.save()
                    member_form.save()
                    messages.success(request, 'Member information updated successfully!')
                    return redirect('members:detail', pk=member.pk)
            except Exception as e:
                messages.error(request, f'Update failed: {str(e)}')
        else:
            # Surface validation errors to the user for quick diagnosis
            if user_form.errors:
                messages.error(request, f"Account form errors: {user_form.errors.as_text()}")
            if member_form.errors:
                messages.error(request, f"Member form errors: {member_form.errors.as_text()}")
    else:
        user_form = UserEditForm(instance=member.user)
        member_form = MemberEditForm(instance=member)
    
    context = {
        'member': member,
        'user_form': user_form,
        'member_form': member_form
    }
    return render(request, 'members/edit.html', context)

@login_required
def change_status(request, pk):
    """Change member status (activate/deactivate)"""
    member = get_object_or_404(Member, pk=pk)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ['active', 'inactive']:
            member.status = new_status
            member.save()
            action = 'activated' if new_status == 'active' else 'deactivated'
            messages.success(request, f'Member {action} successfully!')
        else:
            messages.error(request, 'Invalid status provided.')
    
    return redirect('members:detail', pk=pk)

@login_required
def member_register_test(request):
    """Ultra-simple test registration"""
    from .forms import UserRegistrationForm, MemberRegistrationForm
    from django.contrib.auth import get_user_model
    from django.db import transaction
    
    User = get_user_model()
    
    if request.method == 'POST':
        # Direct database creation for testing
        try:
            username = request.POST.get('username')
            email = request.POST.get('email')
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            password = request.POST.get('password1')
            
            # Member data
            date_of_birth = request.POST.get('date_of_birth')
            gender = request.POST.get('gender')
            address = request.POST.get('address')
            city = request.POST.get('city')
            occupation = request.POST.get('occupation')
            monthly_savings = request.POST.get('monthly_savings')
            
            print(f"Creating user: {username}, {email}, {first_name}, {last_name}")
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                password=password,
                role='member'
            )
            
            # Create member
            member = Member.objects.create(
                user=user,
                date_of_birth=date_of_birth or '1990-01-01',
                gender=gender or 'M',
                marital_status='single',
                address=address or 'Test Address',
                city=city or 'Test City',
                state='Test State',
                postal_code='12345',
                emergency_contact_name='Test Contact',
                emergency_contact_phone='555-0123',
                occupation=occupation or 'Test Job',
                monthly_savings=monthly_savings or '50000.00',
                registration_fee_amount='100.00'
            )
            
            return HttpResponse(f"SUCCESS! User {user.username} and Member {member.member_id} created!")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return HttpResponse(f"ERROR: {str(e)}")
    
    # Simple HTML form for testing
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Registration</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="p-4">
        <h2>Test Member Registration</h2>
        <form method="post">
            <input type="hidden" name="csrfmiddlewaretoken" value="{}">
            
            <div class="mb-3">
                <label class="form-label">Username *</label>
                <input type="text" name="username" class="form-control" required>
            </div>
            
            <div class="mb-3">
                <label class="form-label">Email *</label>
                <input type="email" name="email" class="form-control" required>
            </div>
            
            <div class="mb-3">
                <label class="form-label">First Name *</label>
                <input type="text" name="first_name" class="form-control" required>
            </div>
            
            <div class="mb-3">
                <label class="form-label">Last Name *</label>
                <input type="text" name="last_name" class="form-control" required>
            </div>
            
            <div class="mb-3">
                <label class="form-label">Password *</label>
                <input type="password" name="password1" class="form-control" required>
            </div>
            
            <div class="mb-3">
                <label class="form-label">Date of Birth</label>
                <input type="date" name="date_of_birth" class="form-control">
            </div>
            
            <div class="mb-3">
                <label class="form-label">Gender</label>
                <select name="gender" class="form-select">
                    <option value="M">Male</option>
                    <option value="F">Female</option>
                </select>
            </div>
            
            <div class="mb-3">
                <label class="form-label">Address</label>
                <input type="text" name="address" class="form-control">
            </div>
            
            <div class="mb-3">
                <label class="form-label">City</label>
                <input type="text" name="city" class="form-control">
            </div>
            
            <div class="mb-3">
                <label class="form-label">Occupation</label>
                <input type="text" name="occupation" class="form-control">
            </div>
            
            <div class="mb-3">
                <label class="form-label">Monthly Savings</label>
                <input type="number" name="monthly_savings" class="form-control" step="0.01">
            </div>
            
            <button type="submit" class="btn btn-primary">Register Member (Test)</button>
        </form>
    </body>
    </html>
    '''.format(request.META.get('CSRF_COOKIE', ''))
    
    return HttpResponse(html)

@login_required
@require_http_methods(["POST"])
def update_monthly_deposit(request, member_id):
    """Update member's monthly deposit amount"""
    try:
        member = get_object_or_404(Member, pk=member_id)
        new_amount = Decimal(request.POST.get('monthly_deposit', 0))
        
        if new_amount < 0:
            return JsonResponse({
                'success': False,
                'message': 'Monthly deposit cannot be negative'
            })
        
        old_amount = member.monthly_savings
        member.monthly_savings = new_amount
        member.save()
        
        # Log the change
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        return JsonResponse({
            'success': True,
            'message': f'Monthly deposit updated from ₦{old_amount:,.2f} to ₦{new_amount:,.2f}',
            'new_amount': float(new_amount),
            'old_amount': float(old_amount)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error updating monthly deposit: {str(e)}'
        })

@login_required
def get_member_loan_info(request, member_id):
    """Get member's loan information for AJAX requests"""
    try:
        member = get_object_or_404(Member, pk=member_id)
        
        # Get loan progress
        loan_progress = member.get_loan_progress()
        
        # Get maximum loan amount
        max_loan = member.maximum_loan_amount
        
        # Get current monthly deposit
        monthly_deposit = member.monthly_savings
        
        # Get total savings
        total_savings = 0
        try:
            if hasattr(member, 'savings_account') and member.savings_account:
                total_savings = float(member.savings_account.get_total_savings())
        except:
            total_savings = 0
        
        # Get outstanding loan amount
        outstanding_loan = 0
        if loan_progress['has_active_loan']:
            outstanding_loan = float(loan_progress['remaining_balance'])
        
        return JsonResponse({
            'success': True,
            'member_id': member.member_id,
            'member_name': member.user.get_full_name(),
            'monthly_deposit': float(monthly_deposit),
            'max_loan_amount': float(max_loan),
            'total_savings': total_savings,
            'outstanding_loan': outstanding_loan,
            'loan_progress': loan_progress
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error getting member info: {str(e)}'
        })
