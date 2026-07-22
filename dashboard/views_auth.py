from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Q
from .forms import LoginForm, RegisterForm

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    next_url = request.GET.get('next') or request.POST.get('next') or 'dashboard:index'

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username_or_email = form.cleaned_data['username'].strip()
            password = form.cleaned_data['password']

            # Lookup user by username or email
            lookup_user = User.objects.filter(
                Q(username__iexact=username_or_email) | Q(email__iexact=username_or_email)
            ).first()

            user = None
            if lookup_user:
                user = authenticate(request, username=lookup_user.username, password=password)

            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect(next_url)
            else:
                # Check if account exists and password matches but user is not active (pending approval)
                if lookup_user and lookup_user.check_password(password) and not lookup_user.is_active:
                    messages.warning(
                        request,
                        "Your account is currently pending admin approval. Please contact an administrator to approve your account."
                    )
                else:
                    messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm()

    return render(request, 'dashboard/auth/login.html', {
        'form': form,
        'next': next_url
    })

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                f"Account for '{user.username}' created successfully! Your account is currently pending admin approval."
            )
            return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
    else:
        form = RegisterForm()

    return render(request, 'dashboard/auth/register.html', {'form': form})

def logout_view(request):
    if request.user.is_authenticated:
        logout(request)
        messages.info(request, "You have been logged out successfully.")
    return redirect('login')
