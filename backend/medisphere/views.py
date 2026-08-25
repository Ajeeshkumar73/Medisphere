import json
from django.db import models as db_models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.views.decorators.http import require_POST
from .models import UserProfile, FamilyMember, MedicalDocument, Medicine, PrescriptionOrder, MedicineOrder, LabTest, LabAppointment, Notification, Expense
from .ai_services import analyze_medical_document, generate_member_ai_summary



def landing_page(request):
    from .models import Review
    reviews = Review.objects.all()[:10]
    return render(request, 'landing_page.html', {'reviews': reviews})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('user_dashboard')

    if request.method == 'POST':
        role = request.POST.get('role', 'user')

        if role == 'user':
            full_name = request.POST.get('full_name', '').strip()
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '').strip()
            phone = request.POST.get('phone', '').strip()

            if not full_name or not email or not password:
                messages.error(request, 'Please fill in all required fields.')
                return render(request, 'register_page.html')

            if User.objects.filter(email=email).exists():
                messages.error(request, 'An account with this email already exists.')
                return render(request, 'register_page.html')

            name_parts = full_name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''

            user = User.objects.create_user(
                username=email, email=email, password=password,
                first_name=first_name, last_name=last_name,
            )
            UserProfile.objects.create(user=user, role='user', phone=phone)

        else:
            business_name = request.POST.get('business_name', '').strip()
            license_number = request.POST.get('license_number', '').strip()
            pro_email = request.POST.get('pro_email', '').strip()
            pro_password = request.POST.get('pro_password', '').strip()

            if not business_name or not pro_email or not pro_password:
                messages.error(request, 'Please fill in all required fields.')
                return render(request, 'register_page.html')

            if User.objects.filter(email=pro_email).exists():
                messages.error(request, 'An account with this email already exists.')
                return render(request, 'register_page.html')

            user = User.objects.create_user(
                username=pro_email, email=pro_email, password=pro_password,
                first_name=business_name,
            )
            UserProfile.objects.create(
                user=user, role=role,
                business_name=business_name, license_number=license_number,
            )

        messages.success(request, f'Account created! Please sign in, {user.first_name}.')
        return redirect('login')

    return render(request, 'register_page.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('user_dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        if not email or not password:
            messages.error(request, 'Please enter your email and password.')
            return render(request, 'login_page.html')

        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            # If first login, send to profile setup first
            try:
                profile = user.profile
                if not profile.first_login_done:
                    profile.first_login_done = True
                    profile.save(update_fields=['first_login_done'])
                    return redirect('user_profile')
            except UserProfile.DoesNotExist:
                pass
            return redirect('user_dashboard')
        else:
            messages.error(request, 'Invalid email or password. Please try again.')
            return render(request, 'login_page.html')

    return render(request, 'login_page.html')


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required(login_url='login')
def user_profile_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if profile.role in ['medical_store', 'laboratory']:
        return store_profile_view(request, profile)

    family_members = profile.family_members.all().order_by('created_at')

    if request.method == 'POST':
        action = request.POST.get('action', 'save_profile')

        if action == 'save_profile':
            # ---- Personal info ----
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            if first_name:
                request.user.first_name = first_name
                request.user.last_name = last_name
                request.user.save()

            profile.phone = request.POST.get('phone', profile.phone)
            profile.date_of_birth = request.POST.get('date_of_birth') or None
            profile.age = request.POST.get('age') or None
            profile.gender = request.POST.get('gender') or None
            profile.address = request.POST.get('address', '').strip() or None

            # ---- Vitals ----
            profile.blood_group = request.POST.get('blood_group') or None
            profile.height_cm = request.POST.get('height_cm') or None
            profile.weight_kg = request.POST.get('weight_kg') or None
            profile.disease_name = request.POST.get('disease_name', '').strip() or None
            profile.treatment_duration_years = request.POST.get('treatment_duration_years') or None

            # ---- Allergies ----
            profile.allergy_medicine = request.POST.get('allergy_medicine', '').strip() or None
            profile.allergy_food = request.POST.get('allergy_food', '').strip() or None
            profile.allergy_other = request.POST.get('allergy_other', '').strip() or None

            # ---- Emergency contact ----
            profile.emergency_contact_name = request.POST.get('emergency_contact_name', '').strip() or None
            profile.emergency_contact_phone = request.POST.get('emergency_contact_phone', '').strip() or None

            # ---- Doctor ----
            profile.doctor_name = request.POST.get('doctor_name', '').strip() or None
            profile.doctor_specialization = request.POST.get('doctor_specialization', '').strip() or None
            profile.doctor_phone = request.POST.get('doctor_phone', '').strip() or None
            profile.doctor_hospital = request.POST.get('doctor_hospital', '').strip() or None

            profile.profile_completed = True
            profile.save()  # triggers BMI auto-calculation

            messages.success(request, 'Profile saved successfully!')
            return redirect('user_dashboard')

        elif action == 'add_family_member':
            full_name = request.POST.get('fm_full_name', '').strip()
            relation = request.POST.get('fm_relation', '')
            if full_name and relation:
                FamilyMember.objects.create(
                    profile=profile,
                    full_name=full_name,
                    relation=relation,
                    date_of_birth=request.POST.get('fm_dob') or None,
                    age=request.POST.get('fm_age') or None,
                    gender=request.POST.get('fm_gender') or None,
                    blood_group=request.POST.get('fm_blood_group') or None,
                    phone=request.POST.get('fm_phone', '').strip() or None,
                    address=request.POST.get('fm_address', '').strip() or None,
                    height_cm=request.POST.get('fm_height_cm') or None,
                    weight_kg=request.POST.get('fm_weight_kg') or None,
                    disease_name=request.POST.get('fm_disease_name', '').strip() or None,
                    treatment_duration_years=request.POST.get('fm_treatment_duration_years') or None,
                    medical_conditions=request.POST.get('fm_conditions', '').strip() or None,
                    allergy_medicine=request.POST.get('fm_allergy_medicine', '').strip() or None,
                    allergy_food=request.POST.get('fm_allergy_food', '').strip() or None,
                    allergy_other=request.POST.get('fm_allergy_other', '').strip() or None,
                    emergency_contact_name=request.POST.get('fm_emergency_contact_name', '').strip() or None,
                    emergency_contact_phone=request.POST.get('fm_emergency_contact_phone', '').strip() or None,
                    doctor_name=request.POST.get('fm_doctor_name', '').strip() or None,
                    doctor_specialization=request.POST.get('fm_doctor_specialization', '').strip() or None,
                    doctor_phone=request.POST.get('fm_doctor_phone', '').strip() or None,
                    doctor_hospital=request.POST.get('fm_doctor_hospital', '').strip() or None,
                )
                messages.success(request, f'{full_name} added to family members with full medical profile.')
            else:
                messages.error(request, 'Name and relation are required for a family member.')
            return redirect('user_profile')

        elif action == 'edit_family_member':
            member_id = request.POST.get('member_id')
            fm = get_object_or_404(FamilyMember, id=member_id, profile=profile)
            full_name = request.POST.get('fm_full_name', '').strip()
            relation = request.POST.get('fm_relation', '')
            if full_name and relation:
                fm.full_name = full_name
                fm.relation = relation
                fm.date_of_birth = request.POST.get('fm_dob') or None
                fm.age = request.POST.get('fm_age') or None
                fm.gender = request.POST.get('fm_gender') or None
                fm.blood_group = request.POST.get('fm_blood_group') or None
                fm.phone = request.POST.get('fm_phone', '').strip() or None
                fm.address = request.POST.get('fm_address', '').strip() or None
                fm.height_cm = request.POST.get('fm_height_cm') or None
                fm.weight_kg = request.POST.get('fm_weight_kg') or None
                fm.disease_name = request.POST.get('fm_disease_name', '').strip() or None
                fm.treatment_duration_years = request.POST.get('fm_treatment_duration_years') or None
                fm.medical_conditions = request.POST.get('fm_conditions', '').strip() or None
                fm.allergy_medicine = request.POST.get('fm_allergy_medicine', '').strip() or None
                fm.allergy_food = request.POST.get('fm_allergy_food', '').strip() or None
                fm.allergy_other = request.POST.get('fm_allergy_other', '').strip() or None
                fm.emergency_contact_name = request.POST.get('fm_emergency_contact_name', '').strip() or None
                fm.emergency_contact_phone = request.POST.get('fm_emergency_contact_phone', '').strip() or None
                fm.doctor_name = request.POST.get('fm_doctor_name', '').strip() or None
                fm.doctor_specialization = request.POST.get('fm_doctor_specialization', '').strip() or None
                fm.doctor_phone = request.POST.get('fm_doctor_phone', '').strip() or None
                fm.doctor_hospital = request.POST.get('fm_doctor_hospital', '').strip() or None
                fm.save()
                messages.success(request, f'{full_name}\'s profile updated successfully.')
            return redirect('user_profile')

        elif action == 'delete_family_member':
            member_id = request.POST.get('member_id')
            FamilyMember.objects.filter(id=member_id, profile=profile).delete()
            messages.success(request, 'Family member removed.')
            return redirect('user_profile')

    myself_qr_code_url = reverse('ai_summary_qr_code', kwargs={'member_type': 'myself', 'member_id': profile.id})
    myself_qr_view_url = request.build_absolute_uri(reverse('ai_summary_qr_view', kwargs={'member_type': 'myself', 'member_id': profile.id}))

    context = {
        'user': request.user,
        'profile': profile,
        'family_members': family_members,
        'is_edit': profile.profile_completed,
        'myself_qr_code_url': myself_qr_code_url,
        'myself_qr_view_url': myself_qr_view_url,
    }
    return render(request, 'user_profile.html', context)


@login_required(login_url='login')
def user_dashboard(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = None

    if profile and profile.role == 'medical_store':
        return redirect('pharmacy_dashboard')

    if profile and profile.role == 'laboratory':
        return redirect('lab_dashboard')

    family_members = profile.family_members.all() if profile else []
    recent_docs = profile.documents.all()[:5] if profile else []

    notifications = []
    unread_count = 0
    upcoming_appointments = []
    upcoming_orders = []
    upcoming_prescriptions = []
    ai_summary = None

    if profile:
        ai_summary = generate_member_ai_summary(profile)
        notifications = Notification.objects.filter(profile=profile)[:20]
        unread_count = Notification.objects.filter(profile=profile, is_read=False).count()
        upcoming_appointments = LabAppointment.objects.filter(
            profile=profile,
            status__in=['pending', 'confirmed']
        ).select_related('lab_test', 'laboratory').order_by('appointment_date')[:5]
        upcoming_orders = MedicineOrder.objects.filter(
            profile=profile,
            status__in=['pending', 'confirmed', 'out_for_delivery']
        ).select_related('medicine', 'pharmacy').order_by('-created_at')[:5]
        upcoming_prescriptions = PrescriptionOrder.objects.filter(
            profile=profile,
            status__in=['pending', 'reviewed']
        ).select_related('pharmacy').order_by('-created_at')[:5]

    context = {
        'user': request.user,
        'profile': profile,
        'family_members': family_members,
        'recent_docs': recent_docs,
        'notifications': notifications,
        'unread_count': unread_count,
        'upcoming_appointments': upcoming_appointments,
        'upcoming_orders': upcoming_orders,
        'upcoming_prescriptions': upcoming_prescriptions,
        'ai_summary': ai_summary,
    }
    return render(request, 'user_dashboard.html', context)


@login_required(login_url='login')
def medical_reports_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if profile.role == 'medical_store':
        return redirect('pharmacy_dashboard')

    docs = profile.documents.all()

    # ── Filter by member ──
    member_filter = request.GET.get('member', '').strip()
    if member_filter:
        if member_filter == 'myself':
            docs = docs.filter(member__isnull=True)
        else:
            docs = docs.filter(member_id=member_filter)

    # ── Search ──
    search_q = request.GET.get('q', '').strip()
    if search_q:
        docs = docs.filter(
            db_models.Q(name__icontains=search_q) |
            db_models.Q(facility__icontains=search_q) |
            db_models.Q(notes__icontains=search_q) |
            db_models.Q(member__full_name__icontains=search_q)
        )

    # ── Filter by type ──
    doc_type = request.GET.get('type', '')
    if doc_type and doc_type != 'all':
        docs = docs.filter(document_type=doc_type)

    # ── Sort ──
    sort = request.GET.get('sort', '-document_date')
    allowed_sorts = [
        'document_date', '-document_date',
        'name', '-name',
        'uploaded_at', '-uploaded_at',
        'member__full_name', '-member__full_name'
    ]
    if sort in allowed_sorts:
        docs = docs.order_by(sort)

    context = {
        'user': request.user,
        'profile': profile,
        'documents': docs,
        'search_q': search_q,
        'current_type': doc_type or 'all',
        'current_sort': sort,
        'current_member': member_filter,
        'family_members': profile.family_members.all(),
        'doc_type_choices': MedicalDocument.DOCUMENT_TYPE_CHOICES,
        'total_count': profile.documents.count(),
    }
    return render(request, 'medical_reports.html', context)


@login_required(login_url='login')
def upload_document_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if profile.role == 'medical_store':
        return redirect('pharmacy_dashboard')

    recent_docs = profile.documents.all()[:5]

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        document_type = request.POST.get('document_type', 'other')
        facility = request.POST.get('facility', '').strip()
        document_date = request.POST.get('document_date') or None
        notes = request.POST.get('notes', '').strip()
        uploaded_file = request.FILES.get('file')
        member_id = request.POST.get('member', '').strip()

        member = None
        if member_id:
            member = get_object_or_404(FamilyMember, id=member_id, profile=profile)

        if not name:
            messages.error(request, 'Document name is required.')
        else:
            # Automatic AI Document Analysis
            has_abnormal, ai_desc = analyze_medical_document(
                uploaded_file=uploaded_file,
                name=name,
                document_type=document_type,
                facility=facility,
                user_notes=notes
            )

            final_notes = f"{notes}\n\n{ai_desc}".strip() if notes else ai_desc

            doc = MedicalDocument.objects.create(
                profile=profile,
                member=member,
                name=name,
                document_type=document_type,
                facility=facility or None,
                document_date=document_date,
                notes=final_notes or None,
                has_abnormal=has_abnormal,
                file=uploaded_file,
            )
            status_text = "Abnormal results detected" if has_abnormal else "Normal results"
            messages.success(request, f'“{doc.name}” uploaded successfully. AI Analysis completed ({status_text}).')
            return redirect('medical_reports')

    context = {
        'user': request.user,
        'profile': profile,
        'recent_docs': recent_docs,
        'doc_type_choices': MedicalDocument.DOCUMENT_TYPE_CHOICES,
        'family_members': profile.family_members.all(),
    }
    return render(request, 'Document_update.html', context)


@login_required(login_url='login')
def delete_document_view(request, doc_id):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        messages.error(request, 'Profile not found.')
        return redirect('medical_reports')

    if profile.role == 'medical_store':
        return redirect('pharmacy_dashboard')

    doc = get_object_or_404(MedicalDocument, id=doc_id, profile=profile)
    if request.method == 'POST':
        doc_name = doc.name
        if doc.file:
            import os
            if os.path.isfile(doc.file.path):
                os.remove(doc.file.path)
        doc.delete()
        messages.success(request, f'\u201c{doc_name}\u201d deleted.')
    return redirect('medical_reports')


# ══════════════════════════════════════════════════════════════════════════════
# PHARMACY SUBSYSTEM VIEWS
# ══════════════════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────────────────
# USER (PATIENT) PORTAL VIEWS
# ──────────────────────────────────────────────────────────────────────────────

@login_required(login_url='login')
def user_pharmacy_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if profile.role == 'medical_store':
        return redirect('pharmacy_dashboard')

    # Fetch available pharmacies (profiles with role='medical_store')
    pharmacies = UserProfile.objects.filter(role='medical_store')
    
    # Selected pharmacy
    selected_pharmacy_id = request.GET.get('pharmacy')
    selected_pharmacy = None
    medicines = []
    
    if selected_pharmacy_id:
        selected_pharmacy = get_object_or_404(UserProfile, id=selected_pharmacy_id, role='medical_store')
        medicines = Medicine.objects.filter(pharmacy=selected_pharmacy)
        
        # Search inside selected pharmacy
        q = request.GET.get('q', '').strip()
        if q:
            medicines = medicines.filter(db_models.Q(name__icontains=q) | db_models.Q(description__icontains=q))
    
    # Load user's orders and prescription uploads
    user_orders = MedicineOrder.objects.filter(profile=profile).order_by('-created_at')
    user_prescriptions = PrescriptionOrder.objects.filter(profile=profile).order_by('-created_at')

    context = {
        'user': request.user,
        'profile': profile,
        'pharmacies': pharmacies,
        'selected_pharmacy': selected_pharmacy,
        'medicines': medicines,
        'user_orders': user_orders,
        'user_prescriptions': user_prescriptions,
        'search_q': request.GET.get('q', '').strip(),
    }
    return render(request, 'user_pharmacy.html', context)


@login_required(login_url='login')
@require_POST
def place_order_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if profile.role == 'medical_store':
        return redirect('pharmacy_dashboard')

    med_id = request.POST.get('medicine_id')
    quantity = int(request.POST.get('quantity', 1))
    delivery_address = request.POST.get('delivery_address', '').strip()
    
    medicine = get_object_or_404(Medicine, id=med_id)
    
    if not medicine.is_home_delivery_available:
        messages.error(request, f"Home delivery is not available for {medicine.name}.")
        return redirect(f"/pharmacy/?pharmacy={medicine.pharmacy.id}")
        
    if medicine.stock_quantity < quantity:
        messages.error(request, f"Insufficient stock. Only {medicine.stock_quantity} left.")
        return redirect(f"/pharmacy/?pharmacy={medicine.pharmacy.id}")
        
    if not delivery_address:
        messages.error(request, "Delivery address is required.")
        return redirect(f"/pharmacy/?pharmacy={medicine.pharmacy.id}")
        
    # Deduct stock and place order
    medicine.stock_quantity -= quantity
    medicine.save()
    
    total_price = medicine.price * quantity
    
    MedicineOrder.objects.create(
        profile=profile,
        pharmacy=medicine.pharmacy,
        medicine=medicine,
        quantity=quantity,
        total_price=total_price,
        delivery_address=delivery_address,
        status='pending'
    )
    
    messages.success(request, f"Order for {quantity}x {medicine.name} placed successfully!")
    return redirect('/pharmacy/')


@login_required(login_url='login')
@require_POST
def upload_prescription_order_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if profile.role == 'medical_store':
        return redirect('pharmacy_dashboard')

    pharmacy_id = request.POST.get('pharmacy_id')
    notes = request.POST.get('notes', '').strip()
    uploaded_file = request.FILES.get('file')
    
    pharmacy = get_object_or_404(UserProfile, id=pharmacy_id, role='medical_store')
    
    if not uploaded_file:
        messages.error(request, "Prescription file is required.")
        return redirect(f"/pharmacy/?pharmacy={pharmacy_id}")
        
    PrescriptionOrder.objects.create(
        profile=profile,
        pharmacy=pharmacy,
        file=uploaded_file,
        notes=notes or None,
        status='pending'
    )
    
    messages.success(request, f"Prescription uploaded successfully to {pharmacy.business_name or pharmacy.user.get_full_name()}!")
    return redirect('/pharmacy/')


# ──────────────────────────────────────────────────────────────────────────────
# PHARMACIST (MERCHANT) PORTAL VIEWS
# ──────────────────────────────────────────────────────────────────────────────

@login_required(login_url='login')
def pharmacy_dashboard_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
        
    if profile.role != 'medical_store':
        messages.error(request, "Access denied. Only pharmacies can access the pharmacy dashboard.")
        return redirect('user_dashboard')
        
    medicines = Medicine.objects.filter(pharmacy=profile).order_by('-created_at')
    
    q = request.GET.get('q', '').strip()
    if q:
        medicines = medicines.filter(db_models.Q(name__icontains=q) | db_models.Q(description__icontains=q))
        
    received_orders = MedicineOrder.objects.filter(pharmacy=profile).order_by('-created_at')
    received_prescriptions = PrescriptionOrder.objects.filter(pharmacy=profile).order_by('-created_at')
    
    total_medicines = medicines.count()
    low_stock_count = medicines.filter(stock_quantity__lte=5).count()
    pending_orders = received_orders.filter(status='pending').count()
    pending_prescriptions = received_prescriptions.filter(status='pending').count()
    
    context = {
        'user': request.user,
        'profile': profile,
        'medicines': medicines,
        'received_orders': received_orders,
        'received_prescriptions': received_prescriptions,
        'total_medicines': total_medicines,
        'low_stock_count': low_stock_count,
        'pending_orders': pending_orders,
        'pending_prescriptions': pending_prescriptions,
        'search_q': q,
    }
    return render(request, 'pharmacy_dashboard.html', context)


@login_required(login_url='login')
@require_POST
def add_medicine_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('login')
        
    if profile.role != 'medical_store':
        return redirect('user_dashboard')
        
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()
    price = request.POST.get('price')
    stock_quantity = request.POST.get('stock_quantity', 0)
    is_home_delivery_available = request.POST.get('is_home_delivery_available') == 'on'
    
    if not name or not price:
        messages.error(request, "Name and price are required.")
    else:
        Medicine.objects.create(
            pharmacy=profile,
            name=name,
            description=description or None,
            price=price,
            stock_quantity=stock_quantity,
            is_home_delivery_available=is_home_delivery_available
        )
        messages.success(request, f"Medicine '{name}' added successfully.")
        
    return redirect('pharmacy_dashboard')


@login_required(login_url='login')
@require_POST
def delete_medicine_view(request, med_id):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('login')
        
    if profile.role != 'medical_store':
        return redirect('user_dashboard')
        
    medicine = get_object_or_404(Medicine, id=med_id, pharmacy=profile)
    name = medicine.name
    medicine.delete()
    messages.success(request, f"Medicine '{name}' deleted.")
    return redirect('pharmacy_dashboard')


@login_required(login_url='login')
@require_POST
def update_order_status_view(request, order_id):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('login')
        
    if profile.role != 'medical_store':
        return redirect('user_dashboard')
        
    order = get_object_or_404(MedicineOrder, id=order_id, pharmacy=profile)
    status = request.POST.get('status')
    
    if status in dict(MedicineOrder.STATUS_CHOICES):
        order.status = status
        order.save()
        messages.success(request, f"Order #{order.id} status updated to {order.get_status_display()}.")
    else:
        messages.error(request, "Invalid status.")
        
    return redirect('pharmacy_dashboard')


@login_required(login_url='login')
@require_POST
def update_prescription_status_view(request, pres_id):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('login')
        
    if profile.role != 'medical_store':
        return redirect('user_dashboard')
        
    prescription = get_object_or_404(PrescriptionOrder, id=pres_id, pharmacy=profile)
    status = request.POST.get('status')
    
    if status in dict(PrescriptionOrder.STATUS_CHOICES):
        prescription.status = status
        prescription.save()
        messages.success(request, f"Prescription status updated to {prescription.get_status_display()}.")
    else:
        messages.error(request, "Invalid status.")
        
    return redirect('pharmacy_dashboard')


@login_required(login_url='login')
def store_profile_view(request, profile):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_store_profile':
            business_name = request.POST.get('business_name', '').strip()
            license_number = request.POST.get('license_number', '').strip()
            phone = request.POST.get('phone', '').strip()
            address = request.POST.get('address', '').strip()
            other_info = request.POST.get('other_info', '').strip()
            business_image = request.FILES.get('business_image')
            clear_image = request.POST.get('clear_image') == 'on'
            
            if business_name:
                profile.business_name = business_name
                profile.license_number = license_number
                profile.phone = phone
                profile.address = address
                profile.other_info = other_info
                
                if clear_image:
                    profile.business_image = None
                elif business_image:
                    profile.business_image = business_image
                    
                profile.profile_completed = True
                profile.save()
                messages.success(request, "Profile updated successfully!")
            else:
                messages.error(request, "Business name is required.")
            return redirect('user_profile')

    context = {
        'user': request.user,
        'profile': profile,
    }
    return render(request, 'store_profile.html', context)


@require_POST
def add_review(request):
    try:
        data = json.loads(request.body)
        name = data.get('name')
        role = data.get('role')
        rating = int(data.get('rating', 5))
        content = data.get('content')
        
        from .models import Review
        review = Review.objects.create(name=name, role=role, rating=rating, content=content)
        
        return JsonResponse({'status': 'success', 'review_id': review.id})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required(login_url='login')
@require_POST
def bulk_upload_medicines_view(request):
    import csv
    from io import TextIOWrapper
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('login')
        
    if profile.role != 'medical_store':
        return redirect('user_dashboard')
        
    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        messages.error(request, "Please choose a CSV or Excel file to upload.")
        return redirect('pharmacy_dashboard')
        
    filename = uploaded_file.name.lower()
    
    if filename.endswith('.csv'):
        try:
            csv_file = TextIOWrapper(uploaded_file.file, encoding='utf-8')
            reader = csv.reader(csv_file)
            # Skip header row if present
            header = next(reader, None)
            
            created_count = 0
            for row in reader:
                if not row or not row[0]:
                    continue
                name = row[0].strip()
                description = row[1].strip() if len(row) > 1 and row[1] else ''
                price_str = row[2].strip() if len(row) > 2 and row[2] else '0'
                stock_str = row[3].strip() if len(row) > 3 and row[3] else '0'
                delivery_str = row[4].strip().lower() if len(row) > 4 and row[4] else 'yes'
                
                if not name:
                    continue
                    
                try:
                    price = float(price_str)
                except ValueError:
                    price = 0.0
                    
                try:
                    stock = int(stock_str)
                except ValueError:
                    stock = 0
                    
                is_delivery = delivery_str in ['yes', 'true', '1', 'y']
                
                Medicine.objects.create(
                    pharmacy=profile,
                    name=name,
                    description=description or None,
                    price=price,
                    stock_quantity=stock,
                    is_home_delivery_available=is_delivery
                )
                created_count += 1
                
            messages.success(request, f"Successfully imported {created_count} medicines from CSV.")
        except Exception as e:
            messages.error(request, f"Error processing CSV file: {str(e)}")
            
    elif filename.endswith('.xlsx'):
        try:
            import openpyxl
        except ImportError:
            messages.error(request, "Excel (.xlsx) import requires openpyxl. Please install it or upload a .csv file instead.")
            return redirect('pharmacy_dashboard')
            
        try:
            wb = openpyxl.load_workbook(uploaded_file)
            sheet = wb.active
            created_count = 0
            
            # Start from row 2 to skip headers
            for row in sheet.iter_rows(min_row=2, values_only=True):
                if not row or not row[0]:
                    continue
                
                name = str(row[0]).strip()
                description = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ''
                
                try:
                    price = float(row[2]) if len(row) > 2 and row[2] is not None else 0.0
                except (ValueError, TypeError):
                    price = 0.0
                    
                try:
                    stock = int(row[3]) if len(row) > 3 and row[3] is not None else 0
                except (ValueError, TypeError):
                    stock = 0
                    
                is_delivery = True
                if len(row) > 4 and row[4] is not None:
                    del_val = str(row[4]).strip().lower()
                    is_delivery = del_val in ['yes', 'true', '1', 'y']
                    
                Medicine.objects.create(
                    pharmacy=profile,
                    name=name,
                    description=description or None,
                    price=price,
                    stock_quantity=stock,
                    is_home_delivery_available=is_delivery
                )
                created_count += 1
                
            messages.success(request, f"Successfully imported {created_count} medicines from Excel.")
        except Exception as e:
            messages.error(request, f"Error processing Excel file: {str(e)}")
            
    else:
        messages.error(request, "Unsupported file format. Please upload a .csv or .xlsx file.")
        
    return redirect('pharmacy_dashboard')


# ─────────────────────────────────────────────────────────────
#  LABORATORY SUBSYSTEM
# ─────────────────────────────────────────────────────────────

@login_required(login_url='login')
def lab_dashboard_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('login')

    if profile.role != 'laboratory':
        return redirect('user_dashboard')

    search_q = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '')

    lab_tests = LabTest.objects.filter(laboratory=profile)
    if search_q:
        lab_tests = lab_tests.filter(name__icontains=search_q)
    if category_filter:
        lab_tests = lab_tests.filter(category=category_filter)

    appointments = LabAppointment.objects.filter(laboratory=profile).select_related(
        'profile__user', 'lab_test'
    )

    total_tests = LabTest.objects.filter(laboratory=profile).count()
    pending_appts = appointments.filter(status='pending').count()
    confirmed_appts = appointments.filter(status='confirmed').count()
    home_collection_appts = appointments.filter(is_home_collection=True).count()

    context = {
        'user': request.user,
        'profile': profile,
        'lab_tests': lab_tests,
        'appointments': appointments,
        'total_tests': total_tests,
        'pending_appts': pending_appts,
        'confirmed_appts': confirmed_appts,
        'home_collection_appts': home_collection_appts,
        'search_q': search_q,
        'category_filter': category_filter,
        'category_choices': LabTest.CATEGORY_CHOICES,
    }
    return render(request, 'lab_dashboard.html', context)


@login_required(login_url='login')
@require_POST
def add_lab_test_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('login')

    if profile.role != 'laboratory':
        return redirect('user_dashboard')

    name = request.POST.get('name', '').strip()
    category = request.POST.get('category', 'other')
    description = request.POST.get('description', '').strip()
    price_str = request.POST.get('price', '0')
    turnaround_str = request.POST.get('turnaround_hours', '').strip()
    is_available = request.POST.get('is_available') == 'on'
    is_home = request.POST.get('is_home_sample_collection') == 'on'

    if not name:
        messages.error(request, "Test/Scan name is required.")
        return redirect('lab_dashboard')

    try:
        price = float(price_str)
    except ValueError:
        price = 0.0

    turnaround = int(turnaround_str) if turnaround_str.isdigit() else None

    LabTest.objects.create(
        laboratory=profile,
        name=name,
        category=category,
        description=description or None,
        price=price,
        is_available=is_available,
        is_home_sample_collection=is_home,
        turnaround_hours=turnaround,
    )
    messages.success(request, f'"{name}" added to your test catalogue.')
    return redirect('lab_dashboard')


@login_required(login_url='login')
@require_POST
def delete_lab_test_view(request, test_id):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('login')

    if profile.role != 'laboratory':
        return redirect('user_dashboard')

    test = get_object_or_404(LabTest, id=test_id, laboratory=profile)
    test.delete()
    messages.success(request, "Test removed from catalogue.")
    return redirect('lab_dashboard')


@login_required(login_url='login')
@require_POST
def update_appointment_status_view(request, appt_id):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('login')

    if profile.role != 'laboratory':
        return redirect('user_dashboard')

    appt = get_object_or_404(LabAppointment, id=appt_id, laboratory=profile)
    status = request.POST.get('status')
    if status in dict(LabAppointment.STATUS_CHOICES):
        old_status = appt.status
        appt.status = status
        appt.save()
        messages.success(request, f"Appointment #{appt.id} updated to {appt.get_status_display()}.")

        # ── Send notification to patient ──
        notif_map = {
            'confirmed':       ('lab_confirmed', 'Appointment Confirmed',
                                f'Your appointment for "{appt.lab_test.name}" on {appt.appointment_date} has been confirmed by {profile.business_name or profile.user.get_full_name()}.'),
            'cancelled':       ('lab_cancelled', 'Appointment Cancelled',
                                f'Your appointment for "{appt.lab_test.name}" on {appt.appointment_date} was cancelled. Please contact the lab for more info.'),
            'report_ready':    ('lab_report',    'Report Ready',
                                f'Your lab report for "{appt.lab_test.name}" is ready. Visit the lab portal to access your results.'),
            'sample_collected':('lab_sample',    'Sample Collected',
                                f'Sample for "{appt.lab_test.name}" has been collected. Your report will be ready soon.'),
        }
        if status in notif_map and status != old_status:
            ntype, title, msg = notif_map[status]
            lab_id_param = f'/lab/?lab={profile.id}'
            Notification.objects.create(
                profile=appt.profile,
                notif_type=ntype,
                title=title,
                message=msg,
                link=lab_id_param,
            )
    else:
        messages.error(request, "Invalid status.")
    return redirect('lab_dashboard')


@login_required(login_url='login')
def user_lab_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = None

    if profile and profile.role == 'laboratory':
        return redirect('lab_dashboard')
    if profile and profile.role == 'medical_store':
        return redirect('pharmacy_dashboard')

    lab_id = request.GET.get('lab')
    search_q = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '')

    laboratories = UserProfile.objects.filter(role='laboratory')
    selected_lab = None
    lab_tests = []
    user_appointments = []

    if lab_id:
        selected_lab = get_object_or_404(UserProfile, id=lab_id, role='laboratory')
        lab_tests = LabTest.objects.filter(laboratory=selected_lab, is_available=True)
        if search_q:
            lab_tests = lab_tests.filter(name__icontains=search_q)
        if category_filter:
            lab_tests = lab_tests.filter(category=category_filter)

        if profile:
            user_appointments = LabAppointment.objects.filter(
                profile=profile, laboratory=selected_lab
            ).select_related('lab_test').order_by('-created_at')

    context = {
        'user': request.user,
        'profile': profile,
        'laboratories': laboratories,
        'selected_lab': selected_lab,
        'lab_tests': lab_tests,
        'user_appointments': user_appointments,
        'search_q': search_q,
        'category_filter': category_filter,
        'category_choices': LabTest.CATEGORY_CHOICES,
    }
    return render(request, 'user_lab.html', context)


@login_required(login_url='login')
@require_POST
def book_appointment_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = None

    if not profile or profile.role != 'user':
        messages.error(request, "Only patient accounts can book appointments.")
        return redirect('user_lab')

    test_id = request.POST.get('test_id')
    lab_id = request.POST.get('lab_id')
    appointment_date = request.POST.get('appointment_date')
    appointment_time = request.POST.get('appointment_time') or None
    is_home = request.POST.get('is_home_collection') == 'on'
    collection_address = request.POST.get('collection_address', '').strip()
    notes = request.POST.get('notes', '').strip()

    if not test_id or not appointment_date:
        messages.error(request, "Test and appointment date are required.")
        return redirect(f'/lab/?lab={lab_id}')

    lab_test = get_object_or_404(LabTest, id=test_id, is_available=True)
    laboratory = lab_test.laboratory

    if is_home and not lab_test.is_home_sample_collection:
        messages.error(request, "Home sample collection is not available for this test.")
        return redirect(f'/lab/?lab={lab_id}')

    LabAppointment.objects.create(
        profile=profile,
        laboratory=laboratory,
        lab_test=lab_test,
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        is_home_collection=is_home,
        collection_address=collection_address if is_home else None,
        notes=notes or None,
    )
    messages.success(request, f'Appointment for "{lab_test.name}" booked successfully!')
    return redirect(f'/lab/?lab={lab_id}')


@login_required(login_url='login')
@require_POST
def mark_notifications_read(request):
    """Mark all unread notifications as read for the logged-in user."""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('user_dashboard')
    Notification.objects.filter(profile=profile, is_read=False).update(is_read=True)
    return redirect('user_dashboard')


# ─────────────── GLOBAL DASHBOARD SEARCH ───────────────

@login_required(login_url='login')
def dashboard_search_view(request):
    """AJAX live-search across pharmacy medicines and lab tests."""
    q = request.GET.get('q', '').strip()
    results = {'medicines': [], 'lab_tests': []}

    if len(q) >= 2:
        # Search medicines by name or pharmacy name
        medicines = Medicine.objects.filter(
            db_models.Q(name__icontains=q) |
            db_models.Q(pharmacy__business_name__icontains=q)
        ).select_related('pharmacy').filter(stock_quantity__gt=0)[:8]

        for m in medicines:
            results['medicines'].append({
                'id': m.id,
                'name': m.name,
                'pharmacy': m.pharmacy.business_name or m.pharmacy.user.get_full_name(),
                'pharmacy_id': m.pharmacy.id,
                'price': str(m.price),
                'home_delivery': m.is_home_delivery_available,
                'in_stock': m.stock_quantity > 0,
            })

        # Search lab tests by name or lab name
        lab_tests = LabTest.objects.filter(
            db_models.Q(name__icontains=q) |
            db_models.Q(laboratory__business_name__icontains=q)
        ).select_related('laboratory').filter(is_available=True)[:8]

        for t in lab_tests:
            results['lab_tests'].append({
                'id': t.id,
                'name': t.name,
                'category': t.get_category_display(),
                'lab': t.laboratory.business_name or t.laboratory.user.get_full_name(),
                'lab_id': t.laboratory.id,
                'price': str(t.price),
                'home_collection': t.is_home_sample_collection,
            })

    return JsonResponse(results)


@login_required(login_url='login')
def user_appointments_view(request):
    """View and manage patient lab appointments and medicine bookings."""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if profile.role == 'laboratory':
        return redirect('lab_dashboard')
    if profile.role == 'medical_store':
        return redirect('pharmacy_dashboard')

    appointments = LabAppointment.objects.filter(profile=profile).select_related(
        'lab_test', 'laboratory'
    ).order_by('-appointment_date', '-created_at')

    medicine_orders = MedicineOrder.objects.filter(profile=profile).select_related(
        'medicine', 'pharmacy'
    ).order_by('-created_at')

    prescription_orders = PrescriptionOrder.objects.filter(profile=profile).select_related(
        'pharmacy'
    ).order_by('-created_at')

    context = {
        'user': request.user,
        'profile': profile,
        'appointments': appointments,
        'medicine_orders': medicine_orders,
        'prescription_orders': prescription_orders,
    }
    return render(request, 'user_appointments.html', context)


@login_required(login_url='login')
@require_POST
def cancel_appointment_view(request, appt_id):
    """Cancel a pending/confirmed lab appointment by patient."""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('login')

    if profile.role != 'user':
        messages.error(request, "Only patient accounts can cancel appointments.")
        return redirect('user_dashboard')

    appt = get_object_or_404(LabAppointment, id=appt_id, profile=profile)
    if appt.status in ['pending', 'confirmed']:
        appt.status = 'cancelled'
        appt.save()
        
        # Fire notification to lab owner
        Notification.objects.create(
            profile=appt.laboratory,
            notif_type='lab_cancelled',
            title='❌ Appointment Cancelled by Patient',
            message=f'Patient {request.user.get_full_name()} has cancelled the appointment for "{appt.lab_test.name}" scheduled on {appt.appointment_date}.',
            link='/lab/dashboard/'
        )
        
        messages.success(request, f"Appointment for {appt.lab_test.name} has been cancelled.")
    else:
        messages.error(request, "This appointment cannot be cancelled anymore.")

    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('user_appointments')


@login_required(login_url='login')
@require_POST
def cancel_medicine_order_view(request, order_id):
    """Cancel a pending medicine order by patient."""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('login')

    if profile.role != 'user':
        messages.error(request, "Only patient accounts can cancel orders.")
        return redirect('user_dashboard')

    order = get_object_or_404(MedicineOrder, id=order_id, profile=profile)
    if order.status == 'pending':
        order.status = 'cancelled'
        order.save()
        
        # Restore stock quantity
        med = order.medicine
        med.stock_quantity += order.quantity
        med.save()
        
        # Fire notification to pharmacy owner
        Notification.objects.create(
            profile=order.pharmacy,
            notif_type='order_cancelled',
            title='Order Cancelled by Patient',
            message=f'Patient {request.user.get_full_name()} has cancelled order #{order.id} for "{order.medicine.name}".',
            link='/pharmacy/dashboard/'
        )
        
        messages.success(request, f"Order for {order.medicine.name} has been cancelled.")
    else:
        messages.error(request, "This order cannot be cancelled anymore.")

    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('user_appointments')


# ══════════════════════════════════════════════════════════════════════════════
# EXPENSE MANAGEMENT VIEWS
# ══════════════════════════════════════════════════════════════════════════════

@login_required(login_url='login')
def expenses_view(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if profile.role == 'medical_store':
        return redirect('pharmacy_dashboard')
    if profile.role == 'laboratory':
        return redirect('lab_dashboard')

    if request.method == 'POST':
        amount = request.POST.get('amount')
        purpose = request.POST.get('purpose', '').strip()
        category = request.POST.get('category', 'Others')
        expense_date = request.POST.get('date')

        if not amount or not purpose or not expense_date:
            messages.error(request, "Amount, purpose, and date are required.")
        else:
            try:
                Expense.objects.create(
                    profile=profile,
                    amount=amount,
                    purpose=purpose,
                    category=category,
                    date=expense_date
                )
                messages.success(request, "Expense added successfully!")
            except Exception as e:
                messages.error(request, f"Error adding expense: {e}")
            return redirect('expenses')

    # Fetch all expenses
    expenses = Expense.objects.filter(profile=profile).order_by('-date', '-created_at')

    # Calculate statistics
    from datetime import date, timedelta
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())  # Monday
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)

    total_week = expenses.filter(date__gte=start_of_week).aggregate(db_models.Sum('amount'))['amount__sum'] or 0
    total_month = expenses.filter(date__gte=start_of_month).aggregate(db_models.Sum('amount'))['amount__sum'] or 0
    total_year = expenses.filter(date__gte=start_of_year).aggregate(db_models.Sum('amount'))['amount__sum'] or 0
    total_all = expenses.aggregate(db_models.Sum('amount'))['amount__sum'] or 0

    # Group expenses by category
    category_spending = expenses.values('category').annotate(total=db_models.Sum('amount')).order_by('-total')
    highest_category = category_spending[0] if category_spending else None

    # Group expenses by purpose to show highest purpose
    purpose_spending = expenses.values('purpose').annotate(total=db_models.Sum('amount')).order_by('-total')
    highest_purpose = purpose_spending[0] if purpose_spending else None

    categories = ['Pharmacy', 'Laboratory', 'Hospital', 'Consultation', 'Others']

    context = {
        'user': request.user,
        'profile': profile,
        'expenses': expenses,
        'total_week': total_week,
        'total_month': total_month,
        'total_year': total_year,
        'total_all': total_all,
        'highest_category': highest_category,
        'highest_purpose': highest_purpose,
        'categories': categories,
        'today_str': today.strftime('%Y-%m-%d'),
    }
    return render(request, 'expenses.html', context)


@login_required(login_url='login')
@require_POST
def delete_expense_view(request, expense_id):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('login')
    expense = get_object_or_404(Expense, id=expense_id, profile=profile)
    purpose = expense.purpose
    amount = expense.amount
    expense.delete()
    messages.success(request, f"Expense '{purpose}' (₹{amount}) deleted successfully.")
    return redirect('expenses')

@login_required(login_url='login')
def ai_analyser(request):
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    if request.method == 'POST':
        # Handle document upload directly from AI Analyser page
        name = request.POST.get('name', '').strip()
        document_type = request.POST.get('document_type', 'other')
        facility = request.POST.get('facility', '').strip()
        notes = request.POST.get('notes', '').strip()
        doc_date = request.POST.get('document_date') or None
        target_member_type = request.POST.get('target_member_type', 'myself')
        target_member_id = request.POST.get('target_member_id')
        uploaded_file = request.FILES.get('file')

        target_member = None
        if target_member_type == 'member' and target_member_id:
            target_member = get_object_or_404(FamilyMember, id=target_member_id, profile=profile)

        if not uploaded_file:
            messages.error(request, "Please select a document file to upload.")
        else:
            if not name:
                name = uploaded_file.name

            # AI Clinical Analysis Scan
            has_abnormal, ai_desc = analyze_medical_document(
                uploaded_file=uploaded_file,
                name=name,
                document_type=document_type,
                facility=facility,
                user_notes=notes
            )

            # Create MedicalDocument record
            MedicalDocument.objects.create(
                profile=profile,
                member=target_member,
                name=name,
                document_type=document_type,
                file=uploaded_file,
                facility=facility or None,
                document_date=doc_date,
                notes=f"{notes}\n[AI Scan Result: {ai_desc}]".strip() if notes else f"[AI Scan Result: {ai_desc}]",
                has_abnormal=has_abnormal
            )
            messages.success(request, f"Document '{name}' uploaded & analyzed successfully by AI!")
            
            # Preserve target member in redirect URL
            m_param = f"member={target_member.id}" if target_member else "member=myself"
            return redirect(f"/AI_analyser/?{m_param}")

    # GET Request processing
    member_param = request.GET.get('member', 'myself')
    family_members = profile.family_members.all()
    selected_member = None
    selected_member_type = 'myself'
    selected_member_id = profile.id

    if member_param != 'myself' and member_param.isdigit():
        selected_member = get_object_or_404(FamilyMember, id=int(member_param), profile=profile)
        selected_member_type = 'member'
        selected_member_id = selected_member.id

    # Generate complete AI Summary for selected member
    ai_summary = generate_member_ai_summary(profile=profile, member=selected_member)

    # QR & Download links
    qr_view_url = request.build_absolute_uri(
        reverse('ai_summary_qr_view', kwargs={'member_type': selected_member_type, 'member_id': selected_member_id})
    )
    qr_code_image_url = reverse('ai_summary_qr_code', kwargs={'member_type': selected_member_type, 'member_id': selected_member_id})
    download_url = reverse('download_ai_summary', kwargs={'member_type': selected_member_type, 'member_id': selected_member_id})

    context = {
        'user': request.user,
        'profile': profile,
        'family_members': family_members,
        'selected_member': selected_member,
        'selected_member_type': selected_member_type,
        'selected_member_id': selected_member_id,
        'ai_summary': ai_summary,
        'qr_view_url': qr_view_url,
        'qr_code_image_url': qr_code_image_url,
        'download_url': download_url,
        'doc_type_choices': MedicalDocument.DOCUMENT_TYPE_CHOICES,
    }
    return render(request, 'AI_analyser.html', context)


def ai_summary_qr_code(request, member_type, member_id):
    """Generates PNG QR code image containing clear emergency summary text + public URL."""
    import io
    import qrcode

    member = None
    if member_type == 'member':
        member = get_object_or_404(FamilyMember, id=member_id)
        profile = member.profile
    else:
        profile = get_object_or_404(UserProfile, id=member_id)

    ai_summary = generate_member_ai_summary(profile=profile, member=member)

    qr_view_url = request.build_absolute_uri(
        reverse('ai_summary_qr_view', kwargs={'member_type': member_type, 'member_id': member_id})
    )

    # Construct clean, human-readable text format for instant phone camera scanning
    qr_text_lines = [
        "=== MEDISPHERE EMERGENCY HEALTH SUMMARY ===",
        f"PATIENT: {ai_summary['name']} (ID: {ai_summary['patient_code']})",
        f"BLOOD GROUP: {ai_summary['blood_group']} | AGE: {ai_summary['age']} | GENDER: {ai_summary['gender']}",
        f"EMERGENCY CONTACT: {ai_summary['emergency_contact']} ({ai_summary['emergency_phone']})",
        f"DOCTOR: {ai_summary['doctor_name']} ({ai_summary['doctor_phone']})",
    ]

    if ai_summary['disease_name']:
        qr_text_lines.append(f"CONDITION: {ai_summary['disease_name']} ({ai_summary['treatment_years']} yrs treatment)")
    else:
        qr_text_lines.append("CONDITION: No chronic disease logged")

    if ai_summary['has_allergies']:
        allergies_list = []
        if ai_summary['allergy_medicine']: allergies_list.append(f"Rx: {ai_summary['allergy_medicine']}")
        if ai_summary['allergy_food']: allergies_list.append(f"Food: {ai_summary['allergy_food']}")
        if ai_summary['allergy_other']: allergies_list.append(f"Other: {ai_summary['allergy_other']}")
        qr_text_lines.append(f"CRITICAL ALLERGIES: {', '.join(allergies_list)}")
    else:
        qr_text_lines.append("ALLERGIES: None reported")

    qr_text_lines.append(f"HEALTH INDEX SCORE: {ai_summary['health_index_score']}/100")
    qr_text_lines.append(f"FULL REPORT LINK: {qr_view_url}")

    qr_payload = "\n".join(qr_text_lines)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=5,
        border=2,
    )
    qr.add_data(qr_payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#1e3a8a", back_color="#ffffff")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return HttpResponse(buffer.getvalue(), content_type="image/png")


def ai_summary_qr_view(request, member_type, member_id):
    """Publicly accessible QR scan emergency & health summary page."""
    member = None
    if member_type == 'member':
        member = get_object_or_404(FamilyMember, id=member_id)
        profile = member.profile
    else:
        profile = get_object_or_404(UserProfile, id=member_id)

    ai_summary = generate_member_ai_summary(profile=profile, member=member)
    context = {
        'ai_summary': ai_summary,
        'profile': profile,
        'member': member,
    }
    return render(request, 'ai_summary_qr.html', context)


@login_required(login_url='login')
def download_ai_summary(request, member_type, member_id):
    """Renders printable downloadable report for member AI summary."""
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('login')

    member = None
    if member_type == 'member':
        member = get_object_or_404(FamilyMember, id=member_id, profile=profile)

    ai_summary = generate_member_ai_summary(profile=profile, member=member)
    context = {
        'ai_summary': ai_summary,
        'profile': profile,
        'member': member,
    }
    return render(request, 'ai_summary_download.html', context)