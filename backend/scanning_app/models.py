from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator,MaxValueValidator

# Create your models here.
class ScannedItem(models.Model):
    SCAN_TYPE = [
        ('barcode','Barcode'),
        ('qr','QR Code'),
        ('text','Text'),
        ('image','Image'),
        ('document','Document'),
         ('object', 'Object Recognition')
    ] 

    STATUS_CHOICES = [
        ('pending','Pending'),
        ('processed','Processed'),
        ('archived','Archived')
    ]

    user = models.ForeignKey(User,on_delete=models.CASCADE)
    scan_data = models.TextField(help_text="The actual scanned content")
    scan_type = models.CharField(max_length=20, choices=SCAN_TYPE,help_text="Type of the scanned content")
    timestamp = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20,choices=STATUS_CHOICES,default='pending')
    metadata = models.JSONField(blank=True,default=dict,help_text="Additional scan information")
    image = models.ImageField(upload_to='scans/',blank = True,null=True)
    product_info = models.ForeignKey('ProductInfo',on_delete=models.SET_NULL,null=True,blank=True)
    is_object_detected = models.BooleanField(default=False)
    object_labels = models.JSONField(default=list,blank=True)
    

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['scan_type']),
            models.Index(fields=['status']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['user'])
        ]
    

    def __str__(self):
        return f"{self.scan_type} - {self.scan_data[:50]}"


class UserProfile(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    scan_count = models.IntegerField(default=0)
    free_scans_used = models.IntegerField(default=0)
    max_free_scans = models.IntegerField(default = 5)
    is_premium = models.BooleanField(default = False)
    premium_expiry = models.DateTimeField(null = True,blank =True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def can_scan(self):
        if self.is_premium and self.premium_expiry and self.premium_expiry > timezone.noew():
            return True
        return self.free_scans_used < self.max_free_scans

    def get_remaining_scans(self):
        if self.is_premium and self.premium_expiry and self.premium_expiry>timezone.now():
            return "unlimited"
        return max(0,self.max_free_scans - self.free_scans_used)

    def increment_scan_count(self):
        self.scan_count += 1
        if not self.is_premium:
            self.free_scans_used +=1
        self.save()

    def __str__(self):
        return f"{self.user.username} - {'Premium' if self.is_premium else 'Free'}"
    

class SubscriptionPlan(models.Model):
    
    PLAN_TYPES = [
        ('monthly','Monthly'),
        ('yearly','Yearly'),
        ('lifetime','Lifetime'),
    ]

    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20,choices=PLAN_TYPES)
    price = models.DecimalField(max_digits=10,decimal_places=2)
    razorpay_plan_id = models.CharField(max_length=100,unique=True)
    description = models.TextField()
    features = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.price}"


class Payment(models.Model):
    
    STATUS_CHOICES = [
        ('pending','Pedning'),
        ('success','Success'),
        ('failed','Failed'),
        ('refunded','Refunded'),
    ]

    user = models.ForeignKey(User,on_delete=models.CASCADE)
    subscription_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    razorpay_order_id = models.CharField(max_length=100, unique = True)
    razorpay_payment_id = models.CharField(max_length=100,blank=True,null=True)
    amount = models.DecimalField(max_digits=10,decimal_places=2)
    status = models.CharField(max_length=20,choices=STATUS_CHOICES,default='pending')
    created_at = models.DateTimeField(auto_now_add = True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.user} - {self.subscription_plan.name}"
    

class UserSubscription(models.Model):
    user = models.ForeignKey(User,on_delete = models.CASCADE)
    subscription_plan = models.ForeignKey(SubscriptionPlan,on_delete=models.CASCADE)
    Payment = models.ForeignKey(Payment,on_delete=models.CASCADE)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.name} - {self.subscription_plan.name}"
    

class ProductInfo(models.Model):
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100,blank=True,null=True)
    description = models.TextField(blank=True,null=True)
    brand = models.CharField(blank=True,null=True)
    confidence_score = models.FloatField(default=0.0)
    image_url = models.URLField(blank=True,null=True)
    metadata = models.JSONField(default=dict,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.confidence_score}%)"
