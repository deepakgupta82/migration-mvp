# JWT Service Communication Implementation Plan

## Phase 2: Service Communication Enhancement (Week 3-4)

### 2.1 Backend Service JWT Integration

**File: `backend/app/core/auth.py`**
```python
from jwt_service import jwt_service, ServiceRole

class BackendJWTAuth:
    def __init__(self):
        self.service_token = jwt_service.create_service_token(
            service_name="backend-service",
            service_role=ServiceRole.BACKEND_SERVICE
        )
    
    def get_auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.service_token}"}
    
    async def call_project_service(self, endpoint: str, method: str = "GET", data: dict = None):
        headers = self.get_auth_headers()
        # Make authenticated API calls to project service
        pass

backend_auth = BackendJWTAuth()
```

### 2.2 Reporting Service JWT Integration

**File: `reporting-service/auth.py`**
```python
from jwt_service import jwt_service, ServiceRole

class ReportingJWTAuth:
    def __init__(self):
        self.service_token = jwt_service.create_service_token(
            service_name="reporting-service",
            service_role=ServiceRole.REPORTING_SERVICE
        )
    
    def get_auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.service_token}"}

reporting_auth = ReportingJWTAuth()
```

### 2.3 Frontend JWT Integration

**File: `frontend/src/services/authService.ts`**
```typescript
interface JWTTokens {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
}

class AuthService {
  private tokens: JWTTokens | null = null;
  
  async login(email: string, password: string): Promise<JWTTokens> {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    
    if (response.ok) {
      this.tokens = await response.json();
      localStorage.setItem('tokens', JSON.stringify(this.tokens));
      return this.tokens;
    }
    throw new Error('Login failed');
  }
  
  getAuthHeaders(): Record<string, string> {
    if (!this.tokens) return {};
    return { 'Authorization': `Bearer ${this.tokens.accessToken}` };
  }
  
  async refreshToken(): Promise<void> {
    if (!this.tokens?.refreshToken) throw new Error('No refresh token');
    
    const response = await fetch('/api/auth/refresh', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${this.tokens.refreshToken}` }
    });
    
    if (response.ok) {
      this.tokens = await response.json();
      localStorage.setItem('tokens', JSON.stringify(this.tokens));
    } else {
      this.logout();
      throw new Error('Token refresh failed');
    }
  }
  
  logout(): void {
    this.tokens = null;
    localStorage.removeItem('tokens');
  }
}

export const authService = new AuthService();
```

## Phase 3: OAuth Integration with Settings Toggle (Week 5-6)

### 3.1 OAuth Configuration Model

**File: `project-service/database.py`**
```python
class OAuthConfigurationModel(Base):
    __tablename__ = "oauth_configurations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_name = Column(String(100), nullable=False)  # 'azure', 'google', 'okta'
    client_id = Column(String(255), nullable=False)
    client_secret = Column(Text, nullable=False)  # encrypted
    discovery_url = Column(String(500), nullable=True)
    authorization_url = Column(String(500), nullable=False)
    token_url = Column(String(500), nullable=False)
    userinfo_url = Column(String(500), nullable=False)
    scopes = Column(Text, default='openid email profile')
    is_enabled = Column(Boolean, default=False)
    is_primary = Column(Boolean, default=False)  # Primary OAuth provider
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PlatformAuthSettingsModel(Base):
    __tablename__ = "platform_auth_settings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auth_mode = Column(String(50), default='local')  # 'local', 'oauth', 'hybrid'
    allow_local_auth = Column(Boolean, default=True)
    require_oauth = Column(Boolean, default=False)
    default_user_role = Column(String(50), default='project_user')
    session_timeout_minutes = Column(Integer, default=30)
    updated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 3.2 OAuth Service Implementation

**File: `project-service/oauth_service.py`**
```python
import requests
from urllib.parse import urlencode
from jwt_service import jwt_service

class OAuthService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_authorization_url(self, provider: str, redirect_uri: str, state: str) -> str:
        """Generate OAuth authorization URL"""
        config = self._get_oauth_config(provider)
        if not config or not config.is_enabled:
            raise ValueError(f"OAuth provider {provider} not configured or disabled")
        
        params = {
            'client_id': config.client_id,
            'response_type': 'code',
            'scope': config.scopes,
            'redirect_uri': redirect_uri,
            'state': state
        }
        
        return f"{config.authorization_url}?{urlencode(params)}"
    
    async def handle_oauth_callback(self, provider: str, code: str, redirect_uri: str) -> dict:
        """Handle OAuth callback and create/update user"""
        config = self._get_oauth_config(provider)
        
        # Exchange code for tokens
        token_response = await self._exchange_code_for_tokens(config, code, redirect_uri)
        access_token = token_response.get('access_token')
        
        # Get user info from OAuth provider
        user_info = await self._get_user_info(config, access_token)
        
        # Create or update user in database
        user = await self._create_or_update_oauth_user(provider, user_info)
        
        # Create JWT tokens for the user
        jwt_access_token = jwt_service.create_oauth_token(
            user_id=str(user.id),
            email=user.email,
            provider=provider,
            external_id=user_info.get('sub', user_info.get('id'))
        )
        
        jwt_refresh_token = jwt_service.create_user_refresh_token(str(user.id))
        
        return {
            'access_token': jwt_access_token,
            'refresh_token': jwt_refresh_token,
            'token_type': 'bearer',
            'user': user
        }
```

### 3.3 Settings UI for OAuth Toggle

**File: `frontend/src/components/settings/AuthenticationSettings.tsx`**
```typescript
interface AuthSettings {
  authMode: 'local' | 'oauth' | 'hybrid';
  allowLocalAuth: boolean;
  requireOAuth: boolean;
  oauthProviders: OAuthProvider[];
}

const AuthenticationSettings: React.FC = () => {
  const [settings, setSettings] = useState<AuthSettings>();
  const [oauthEnabled, setOauthEnabled] = useState(false);
  
  const handleToggleOAuth = async (enabled: boolean) => {
    try {
      const response = await fetch('/api/settings/auth', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...authService.getAuthHeaders()
        },
        body: JSON.stringify({
          authMode: enabled ? 'hybrid' : 'local',
          allowLocalAuth: true,
          requireOAuth: enabled
        })
      });
      
      if (response.ok) {
        setOauthEnabled(enabled);
        notifications.show({
          title: 'Authentication Settings Updated',
          message: `OAuth authentication ${enabled ? 'enabled' : 'disabled'}`,
          color: 'green'
        });
      }
    } catch (error) {
      notifications.show({
        title: 'Error',
        message: 'Failed to update authentication settings',
        color: 'red'
      });
    }
  };
  
  return (
    <Card>
      <Stack gap="md">
        <Group justify="space-between">
          <div>
            <Text fw={600}>OAuth Authentication</Text>
            <Text size="sm" c="dimmed">
              Enable OAuth providers for enterprise authentication
            </Text>
          </div>
          <Switch
            checked={oauthEnabled}
            onChange={(event) => handleToggleOAuth(event.currentTarget.checked)}
            label="Enable OAuth"
          />
        </Group>
        
        {oauthEnabled && (
          <OAuthProviderConfiguration />
        )}
      </Stack>
    </Card>
  );
};
```

## Phase 4: Backward Compatibility & Migration (Week 7-8)

### 4.1 Gradual Migration Strategy

1. **Dual Authentication Support**: Both legacy tokens and JWT work simultaneously
2. **Service Token Migration**: Services gradually adopt JWT while maintaining legacy fallback
3. **User Token Migration**: Users get JWT tokens on next login, legacy tokens still work
4. **Configuration Toggle**: Admin can enable/disable OAuth without breaking existing auth

### 4.2 Migration Validation

```python
# Migration validation script
def validate_jwt_migration():
    """Validate that JWT migration doesn't break existing functionality"""
    
    # Test 1: Legacy service tokens still work
    assert test_legacy_service_auth() == True
    
    # Test 2: New JWT service tokens work
    assert test_jwt_service_auth() == True
    
    # Test 3: User authentication works with both methods
    assert test_user_auth_legacy() == True
    assert test_user_auth_jwt() == True
    
    # Test 4: OAuth can be toggled without breaking local auth
    assert test_oauth_toggle() == True
    
    print("✅ All JWT migration tests passed")
```

## Benefits of This Implementation

1. **Zero Breaking Changes**: All existing functionality preserved
2. **Gradual Adoption**: Services can migrate to JWT at their own pace
3. **Enhanced Security**: JWT tokens with proper expiration and refresh
4. **OAuth Ready**: Enterprise OAuth integration with settings toggle
5. **Service Communication**: Secure JWT-based service-to-service auth
6. **Scalability**: Foundation for microservices architecture
7. **Monitoring**: JWT tokens include metadata for better logging/monitoring
