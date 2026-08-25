from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('laboratory', 'Laboratory'),
        ('medical_store', 'Medical Store'),
    ]
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('non_binary', 'Non-binary'),
        ('other', 'Other'),
    ]
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    phone = models.CharField(max_length=20, blank=True, null=True)

    # Professional fields (for laboratory / medical store roles)
    business_name = models.CharField(max_length=200, blank=True, null=True)
    license_number = models.CharField(max_length=100, blank=True, null=True)
    business_image = models.FileField(upload_to='business_images/', blank=True, null=True)
    other_info = models.TextField(blank=True, null=True)

    # Medical profile fields
    date_of_birth = models.DateField(blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    # Vitals
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES, blank=True, null=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    bmi = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)

    # Medical conditions
    disease_name = models.CharField(max_length=200, blank=True, null=True)
    treatment_duration_years = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)

    # Allergies
    allergy_medicine = models.TextField(blank=True, null=True)
    allergy_food = models.TextField(blank=True, null=True)
    allergy_other = models.TextField(blank=True, null=True)

    # Emergency contact
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)

    # Primary consultant
    doctor_name = models.CharField(max_length=100, blank=True, null=True)
    doctor_specialization = models.CharField(max_length=100, blank=True, null=True)
    doctor_phone = models.CharField(max_length=20, blank=True, null=True)
    doctor_hospital = models.CharField(max_length=200, blank=True, null=True)

    # Track if profile has been completed
    profile_completed = models.BooleanField(default=False)
    first_login_done = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.role})"

    def get_patient_id(self):
        return f"MS-{self.user.id:05d}"

    def save(self, *args, **kwargs):
        # Auto-calculate BMI
        if self.height_cm and self.weight_kg:
            h = float(self.height_cm) / 100
            self.bmi = round(float(self.weight_kg) / (h * h), 1)
        super().save(*args, **kwargs)


class FamilyMember(models.Model):
    RELATION_CHOICES = [
        ('spouse', 'Spouse'),
        ('parent', 'Parent'),
        ('child', 'Child'),
        ('sibling', 'Sibling'),
        ('grandparent', 'Grandparent'),
        ('grandchild', 'Grandchild'),
        ('other', 'Other'),
    ]
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ]
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]

    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='family_members')
    full_name = models.CharField(max_length=100)
    relation = models.CharField(max_length=20, choices=RELATION_CHOICES)
    date_of_birth = models.DateField(blank=True, null=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    # Vitals
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    bmi = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)

    # Conditions & Medical details
    disease_name = models.CharField(max_length=200, blank=True, null=True)
    treatment_duration_years = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    medical_conditions = models.TextField(blank=True, null=True)

    # Allergies
    allergy_medicine = models.TextField(blank=True, null=True)
    allergy_food = models.TextField(blank=True, null=True)
    allergy_other = models.TextField(blank=True, null=True)

    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True, null=True)

    # Doctor / Consultant
    doctor_name = models.CharField(max_length=100, blank=True, null=True)
    doctor_specialization = models.CharField(max_length=100, blank=True, null=True)
    doctor_phone = models.CharField(max_length=20, blank=True, null=True)
    doctor_hospital = models.CharField(max_length=200, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} ({self.relation}) - {self.profile.user.get_full_name()}"

    def get_member_id(self):
        return f"FM-{self.id:05d}"

    def save(self, *args, **kwargs):
        if self.height_cm and self.weight_kg:
            h = float(self.height_cm) / 100
            self.bmi = round(float(self.weight_kg) / (h * h), 1)
        super().save(*args, **kwargs)



class MedicalDocument(models.Model):
    DOCUMENT_TYPE_CHOICES = [
        ('lab_report',       'Lab Report'),
        ('imaging',          'Imaging'),
        ('vaccination',      'Vaccination'),
        ('prescription',     'Prescription'),
        ('medical_history',  'Medical History'),
        ('allergy',          'Allergy'),
        ('other',            'Other'),
    ]

    profile = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='documents'
    )
    member = models.ForeignKey(
        FamilyMember, on_delete=models.CASCADE, related_name='documents', blank=True, null=True
    )
    name         = models.CharField(max_length=255)
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES, default='other')
    file         = models.FileField(upload_to='medical_docs/%Y/%m/', blank=True, null=True)
    facility     = models.CharField(max_length=255, blank=True, null=True)   # hospital / lab name
    document_date = models.DateField(blank=True, null=True)
    notes        = models.TextField(blank=True, null=True)
    has_abnormal = models.BooleanField(default=False)   # flag abnormal results
    uploaded_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-document_date', '-uploaded_at']

    def __str__(self):
        return f"{self.name} ({self.get_document_type_display()}) - {self.profile.user.get_full_name()}"

    def file_extension(self):
        if self.file:
            import os
            return os.path.splitext(self.file.name)[1].lower().lstrip('.')
        return ''

    def type_icon(self):
        icons = {
            'lab_report':      'lab_panel',
            'imaging':         'radiology',
            'vaccination':     'vaccines',
            'prescription':    'prescriptions',
            'medical_history': 'history_edu',
            'allergy':         'allergy',
            'other':           'description',
        }
        return icons.get(self.document_type, 'description')

    def type_color(self):
        colors = {
            'lab_report':      'text-secondary',
            'imaging':         'text-primary',
            'vaccination':     'text-green-600',
            'prescription':    'text-orange-500',
            'medical_history': 'text-purple-600',
            'allergy':         'text-error',
            'other':           'text-outline',
        }
        return colors.get(self.document_type, 'text-outline')


class Medicine(models.Model):
    pharmacy = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='medicines')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    is_home_delivery_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.pharmacy.business_name or self.pharmacy.user.get_full_name()}"


class PrescriptionOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('filled', 'Filled'),
        ('rejected', 'Rejected'),
    ]

    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='prescription_orders')
    pharmacy = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='received_prescriptions')
    file = models.FileField(upload_to='prescriptions/%Y/%m/')
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Prescription from {self.profile.user.get_full_name()} to {self.pharmacy.business_name or self.pharmacy.user.get_full_name()}"

    def file_extension(self):
        if self.file:
            import os
            return os.path.splitext(self.file.name)[1].lower().lstrip('.')
        return ''


class MedicineOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('confirmed', 'Confirmed'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='medicine_orders')
    pharmacy = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='received_orders')
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name='orders')
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    delivery_address = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.medicine.name} by {self.profile.user.get_full_name()}"


# ─────────────── LABORATORY SUBSYSTEM ───────────────

class LabTest(models.Model):
    CATEGORY_CHOICES = [
        ('blood_test', 'Blood Test'),
        ('urine_test', 'Urine Test'),
        ('xray', 'X-Ray'),
        ('mri', 'MRI'),
        ('ct_scan', 'CT Scan'),
        ('ultrasound', 'Ultrasound'),
        ('ecg', 'ECG'),
        ('other', 'Other'),
    ]

    laboratory = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='lab_tests'
    )
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='other')
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    is_home_sample_collection = models.BooleanField(default=False)
    turnaround_hours = models.PositiveIntegerField(blank=True, null=True, help_text="Expected result delivery in hours")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()}) — {self.laboratory.business_name or self.laboratory.user.get_full_name()}"


class LabAppointment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Confirmation'),
        ('confirmed', 'Confirmed'),
        ('sample_collected', 'Sample Collected'),
        ('report_ready', 'Report Ready'),
        ('cancelled', 'Cancelled'),
    ]

    profile = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='lab_appointments'
    )
    laboratory = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name='received_appointments'
    )
    lab_test = models.ForeignKey(
        LabTest, on_delete=models.CASCADE, related_name='appointments'
    )
    appointment_date = models.DateField()
    appointment_time = models.TimeField(blank=True, null=True)
    is_home_collection = models.BooleanField(default=False)
    collection_address = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-appointment_date', '-created_at']

    def __str__(self):
        return f"Appt #{self.id} — {self.lab_test.name} for {self.profile.user.get_full_name()} on {self.appointment_date}"


# ─────────────── NOTIFICATION SYSTEM ───────────────

class Notification(models.Model):
    TYPE_CHOICES = [
        ('lab_confirmed',   'Lab Appointment Confirmed'),
        ('lab_cancelled',   'Lab Appointment Cancelled'),
        ('lab_report',      'Lab Report Ready'),
        ('lab_sample',      'Sample Collected'),
        ('pharmacy_order',  'Pharmacy Order Update'),
        ('general',         'General'),
    ]

    profile    = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='notifications')
    notif_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default='general')
    title      = models.CharField(max_length=200)
    message    = models.TextField()
    link       = models.CharField(max_length=300, blank=True, null=True)  # optional deep-link
    is_read    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_notif_type_display()}] → {self.profile.user.get_full_name()}: {self.title}"


# ─────────────── EXPENSE SYSTEM ───────────────

class Expense(models.Model):
    profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='expenses')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    purpose = models.CharField(max_length=255)
    category = models.CharField(max_length=100, default='Others')
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.purpose} — ₹{self.amount} on {self.date}"

class Review(models.Model):
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=50)
    rating = models.PositiveIntegerField(default=5)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.rating} Stars"
