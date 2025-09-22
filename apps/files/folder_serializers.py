from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Folder, File

User = get_user_model()


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user serializer for folder responses"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class FolderSerializer(serializers.ModelSerializer):
    """Basic folder serializer"""
    user = UserBasicSerializer(read_only=True)
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    subfolders_count = serializers.SerializerMethodField()
    files_count = serializers.SerializerMethodField()
    full_path = serializers.CharField(read_only=True)
    
    class Meta:
        model = Folder
        fields = [
            'id', 'name', 'description', 'color', 'user', 'parent', 'parent_name',
            'subfolders_count', 'files_count', 'full_path', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def get_subfolders_count(self, obj):
        return obj.subfolders.filter(deleted_at__isnull=True).count()
    
    def get_files_count(self, obj):
        return obj.files.filter(deleted_at__isnull=True).count()


class FolderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating folders"""
    
    class Meta:
        model = Folder
        fields = ['name', 'description', 'color', 'parent']
    
    def validate_name(self, value):
        """Validate folder name"""
        if not value.strip():
            raise serializers.ValidationError("Folder name cannot be empty")
        
        # Check for invalid characters
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in value:
                raise serializers.ValidationError(
                    f"Folder name cannot contain '{char}'"
                )
        
        return value.strip()
    
    def validate_parent(self, value):
        """Validate parent folder"""
        if value:
            request = self.context.get('request')
            if request and request.user:
                # Ensure parent belongs to the same user
                if value.user != request.user:
                    raise serializers.ValidationError(
                        "Parent folder must belong to the same user"
                    )
                
                # Ensure parent is not deleted
                if value.deleted_at:
                    raise serializers.ValidationError(
                        "Cannot create folder in deleted parent"
                    )
        
        return value
    
    def validate(self, attrs):
        """Validate unique folder name within parent"""
        name = attrs.get('name')
        parent = attrs.get('parent')
        request = self.context.get('request')
        
        if request and request.user:
            # Check for duplicate names in the same parent
            existing = Folder.objects.filter(
                user=request.user,
                parent=parent,
                name__iexact=name,
                deleted_at__isnull=True
            )
            
            if existing.exists():
                raise serializers.ValidationError({
                    'name': 'A folder with this name already exists in the selected location'
                })
        
        return attrs


class FolderDetailSerializer(FolderSerializer):
    """Detailed folder serializer with additional information"""
    subfolders = serializers.SerializerMethodField()
    recent_files = serializers.SerializerMethodField()
    total_size = serializers.SerializerMethodField()
    
    class Meta(FolderSerializer.Meta):
        fields = FolderSerializer.Meta.fields + [
            'subfolders', 'recent_files', 'total_size'
        ]
    
    def get_subfolders(self, obj):
        """Get immediate subfolders"""
        subfolders = obj.subfolders.filter(deleted_at__isnull=True)[:10]
        return FolderSerializer(subfolders, many=True, context=self.context).data
    
    def get_recent_files(self, obj):
        """Get recent files in this folder"""
        files = obj.files.filter(deleted_at__isnull=True).order_by('-created_at')[:5]
        from .serializers import FileSerializer
        return FileSerializer(files, many=True, context=self.context).data
    
    def get_total_size(self, obj):
        """Get total size of all files in folder and subfolders"""
        total_size = 0
        
        # Size of files in this folder
        files_size = obj.files.filter(deleted_at__isnull=True).aggregate(
            total=serializers.models.Sum('file_size')
        )['total'] or 0
        total_size += files_size
        
        # Size of files in subfolders (recursive)
        for subfolder in obj.get_descendants():
            if not subfolder.deleted_at:
                subfolder_size = subfolder.files.filter(deleted_at__isnull=True).aggregate(
                    total=serializers.models.Sum('file_size')
                )['total'] or 0
                total_size += subfolder_size
        
        return total_size


class FolderTreeSerializer(serializers.ModelSerializer):
    """Serializer for folder tree structure"""
    subfolders = serializers.SerializerMethodField()
    files_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Folder
        fields = [
            'id', 'name', 'description', 'color', 'subfolders', 'files_count',
            'created_at', 'updated_at'
        ]
    
    def get_subfolders(self, obj):
        """Recursively get subfolders"""
        subfolders = obj.subfolders.filter(deleted_at__isnull=True)
        return FolderTreeSerializer(subfolders, many=True, context=self.context).data
    
    def get_files_count(self, obj):
        return obj.files.filter(deleted_at__isnull=True).count()


class MoveFolderSerializer(serializers.Serializer):
    """Serializer for moving folders"""
    parent_id = serializers.UUIDField(required=False, allow_null=True)
    
    def validate_parent_id(self, value):
        """Validate parent folder exists and belongs to user"""
        if value:
            request = self.context.get('request')
            if request and request.user:
                try:
                    parent = Folder.objects.get(
                        id=value,
                        user=request.user,
                        deleted_at__isnull=True
                    )
                    return value
                except Folder.DoesNotExist:
                    raise serializers.ValidationError(
                        "Parent folder not found or access denied"
                    )
        
        return value


class FolderStatsSerializer(serializers.Serializer):
    """Serializer for folder statistics"""
    total_folders = serializers.IntegerField()
    total_files = serializers.IntegerField()
    total_size = serializers.IntegerField()
    total_size_human = serializers.CharField()
    folder_depth = serializers.IntegerField()
    largest_folder = serializers.DictField()
    most_files_folder = serializers.DictField()