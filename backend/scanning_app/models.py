from django.db import models

# Create your models here.
class ScannedItem(models.Model):
    SCAN_TYPE = [
        ('barcode','Barcode'),
        ('qr','QR Code'),
        ('text','Text'),
        ('image','Image'),
        ('document','Document')
    ] 

    STATUS_CHOICES = [
        ('pending','Pending'),
        ('processed','Processed'),
        ('archived','Archived')
    ]

    scan_data = models.TextField(help_text="The actual scanned content")
    scan_type = models.CharField(max_length=20, choices=SCAN_TYPE,help_text="Type of the scanned content")
    timestamp = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20,choices=STATUS_CHOICES,default='pending')
    metadata = models.JSONField(blank=True,default=dict,help_text="Additional scan information")
    image = models.ImageField(upload_to='scans/',blank = True,null=True)
    

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['scan_type']),
            models.Index(fields=['status']),
            models.Index(fields=['timestamp']),
        ]
    

    def __str__(self):
        return f"{self.scan_type} - {self.scan_data[:50]}"
    

