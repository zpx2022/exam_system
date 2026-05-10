from rest_framework import serializers
from django.contrib.auth.models import User as DjangoUser
from django.contrib.auth import authenticate
from .models import User


class LoginSerializer(serializers.Serializer):
    """Login serializer"""
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError('Invalid username or password')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            attrs['user'] = user
        else:
            raise serializers.ValidationError('Must include username and password')
        
        return attrs


class RegisterSerializer(serializers.ModelSerializer):
    """Registration serializer"""
    password = serializers.CharField(write_only=True, min_length=6)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'password', 'password_confirm', 'real_name', 'phone', 'role', 'student_class']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        username = validated_data.pop('username')
        user = User.objects.create_user(
            username=username,
            password=password,
            **validated_data
        )
        return user


class UserInfoSerializer(serializers.ModelSerializer):
    """User information serializer"""

    class Meta:
        model = User
        fields = ['id', 'username', 'role', 'is_active',
                  'date_joined']
        read_only_fields = ['id', 'date_joined']


class AdminUserSerializer(UserInfoSerializer):
    """Admin user management serializer"""
    password = serializers.CharField(write_only=True, required=False)
    phone = serializers.SerializerMethodField()
    student_class_name = serializers.CharField(source='student_class.name', read_only=True, allow_null=True)

    courses = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )

    class Meta(UserInfoSerializer.Meta):
        fields = ['id', 'username', 'real_name', 'role', 'is_active',
                  'date_joined', 'password', 'phone', 'student_class_name', 'courses']
        read_only_fields = ['id', 'date_joined']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
        }

    def get_phone(self, instance):
        """Get decrypted phone number"""
        return instance.get_phone()

    def to_representation(self, instance):
        """Override representation to decrypt sensitive fields"""
        data = super().to_representation(instance)
        # Decrypt sensitive fields for output
        data['real_name'] = instance.get_real_name()
        data['phone'] = instance.get_phone()
        return data

    def create(self, validated_data):
        courses = validated_data.pop('courses', None)
        password = validated_data.pop('password', None)
        
        # Get sensitive data from standard fields
        real_name = validated_data.pop('real_name', '')
        phone = validated_data.pop('phone', '')
        
        # Create user
        username = validated_data.pop('username')
        user = User.objects.create_user(
            username=username,
            password=password or 'default123',  # Set default password if not provided
            **validated_data
        )
        
        # Set encrypted fields
        if real_name:
            user.set_real_name(real_name)
        if phone:
            user.set_phone(phone)
        
        if password:
            user.set_password(password)
        user.save()
        
        # Handle courses if provided
        if courses:
            # This would need to be implemented based on your course relationship
            pass
        
        return user

    def update(self, instance, validated_data):
        courses = validated_data.pop('courses', None)
        
        # Handle password
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        
        # Get sensitive data from standard fields
        real_name = validated_data.pop('real_name', None)
        phone = validated_data.pop('phone', None)
        
        # Update encrypted fields
        if real_name is not None:
            instance.set_real_name(real_name)
        if phone is not None:
            instance.set_phone(phone)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Handle courses if provided
        if courses is not None:
            # This would need to be implemented based on your course relationship
            pass
        
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    """Change password serializer"""
    old_password = serializers.CharField(write_only=True)
    code = serializers.CharField(write_only=True, required=False)
    new_password = serializers.CharField(write_only=True, min_length=6)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords don't match")
        return attrs


class ForgotPasswordSendCodeSerializer(serializers.Serializer):
    """Forgot password send code serializer"""
    username = serializers.CharField(max_length=150)

    def validate_username(self, value):
        try:
            User.objects.get(username=value)
        except User.DoesNotExist:
            # For security, don't reveal if user exists
            pass
        return value


class ForgotPasswordResetSerializer(serializers.Serializer):
    """Forgot password reset serializer"""
    username = serializers.CharField(max_length=150)
    code = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs