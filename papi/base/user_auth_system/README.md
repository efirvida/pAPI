# User Authentication and Authorization System

A robust, high-performance user authentication and authorization system implementing both Role-Based Access Control (RBAC) and Attribute-Based Access Control (ABAC) for secure identity and permission management in FastAPI applications.

## Key Features

### Authentication
- **JWT-Based Authentication**
  - Secure token-based authentication with OAuth2
  - Token rotation and automatic expiration
  - Historical key support for graceful key rotation
  - Brute force protection with sliding window rate limiting
  - Configurable token expiration and refresh
  - Password hashing with bcrypt
  - User session management
  - Account lockout protection
  - IP-based security measures

- **Comprehensive Authorization**
  - Role-Based Access Control (RBAC)
  - Attribute-Based Access Control (ABAC)
  - Fine-grained permission management using Casbin policies
  - Dynamic policy evaluation and enforcement
  - Support for role hierarchies
  - Group-based access control

- **User Management**
  - Complete user CRUD operations
  - Group management with hierarchical structure
  - Role assignments and inheritance
  - User activation/deactivation
  - Password management and reset capabilities
  - User profile management (avatar, full name, etc.)

- **Security Features**
  - Comprehensive audit logging of all security events
  - Security event tracking with timestamps
  - Account state management (active/inactive)
  - System lockout protection for critical resources
  - Token rotation and expiration management
  - SQL injection protection through SQLAlchemy
  - XSS protection through FastAPI's automatic response sanitization

## API Endpoints

### Authentication
- `POST /auth/token`
  - **Purpose**: Obtain JWT access token
  - **Input**: OAuth2 form with username and password
  - **Returns**: JWT token with expiration
  - **Security**: Implements brute force protection and account lockout

### Users Management
- `GET /users`
  - **Purpose**: List all users
  - **Parameters**: 
    - `skip`: Number of records to skip (pagination)
    - `limit`: Maximum number of records to return
  - **Returns**: List of user objects with roles and groups
  - **Required Role**: Admin or appropriate read permissions

- `POST /users`
  - **Purpose**: Create new user
  - **Input**: UserCreate schema with:
    - username (required)
    - email (required)
    - password (required)
    - full_name (optional)
    - avatar (optional)
    - is_active (default: true)
    - roles (optional)
    - groups (optional)
  - **Returns**: Created user object
  - **Required Role**: Admin

- `PATCH /users/{user_id}`
  - **Purpose**: Update user details
  - **Parameters**: User ID
  - **Input**: UserUpdate schema with modifiable fields
  - **Returns**: Updated user object
  - **Required Role**: Admin or user self-update

- `DELETE /users/{user_id}`
  - **Purpose**: Delete user
  - **Parameters**: User ID
  - **Returns**: Success message
  - **Required Role**: Admin

### Groups Management
- `GET /groups`
  - **Purpose**: List all groups
  - **Returns**: List of group objects with members
  - **Required Role**: Root or appropriate read permissions

- `POST /groups`
  - **Purpose**: Create new group
  - **Input**: GroupCreate schema with name and description
  - **Returns**: Created group object
  - **Required Role**: Root

- `PATCH /groups/{group_id}`
  - **Purpose**: Update group details
  - **Parameters**: Group ID
  - **Input**: GroupUpdate schema
  - **Returns**: Updated group object
  - **Required Role**: Root

- `DELETE /groups/{group_id}`
  - **Purpose**: Delete group
  - **Parameters**: Group ID
  - **Returns**: Success message
  - **Required Role**: Root

## Security Enums

### Audit Log Keys
- `LOGIN_SUCCESS`: Successful login attempt
- `LOGIN_FAILED`: Failed login attempt
- `ACCOUNT_LOCKED`: Account locked due to multiple failures
- `SYSTEM_LOCKOUT`: System-wide lockout triggered
- `PERMISSION_DENIED`: Access denied to resource
- `KEY_ROTATION`: Security key rotation event
- `LOGIN_INACTIVE`: Login attempt on inactive account
- `ACCESS_ATTEMPT_INACTIVE`: Resource access attempt by inactive user

### Policy Actions
- `ALL`: Wildcard permission for all actions
- `READ`: View or retrieve resources
- `WRITE`: Create or submit new data
- `UPDATE`: Modify existing resources
- `DELETE`: Remove resources
- `PATCH`: Partial update of resources
- `EXECUTE`: Execute commands or operations
- `APPROVE`: Approve actions or resources
- `REJECT`: Reject actions or resources

## Database Schema
- `users`: Core user information and authentication
- `roles`: Role definitions and permissions
- `groups`: Group management
- `user_roles`: Many-to-many user-role relationships
- `user_groups`: Many-to-many user-group relationships
- `auth_rules`: Casbin policy rules storage

## Dependencies

- FastAPI: ^0.100.0 - Modern web framework for building APIs
- SQLAlchemy: ^2.0.0 - SQL toolkit and ORM
- python-jose[cryptography]: ^3.3.0 - JWT token handling
- passlib[bcrypt]: ^1.7.4 - Password hashing
- casbin: ^1.1.1 - Authorization library
- redis: ^4.5.0 (optional) - Distributed caching
- loguru: ^0.7.0 - Advanced logging

## Installation

```bash
# Install from requirements
pip install -r requirements.txt

# Set up environment variables
export SECRET_KEY="your-secret-key"
export ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## Configuration and Security Best Practices

### Environment Variables
```bash
# Required Settings
SECRET_KEY="your-secure-secret-key"              # Min 32 chars
ACCESS_TOKEN_EXPIRE_MINUTES=30                    # Token lifetime
REFRESH_TOKEN_EXPIRE_DAYS=7                       # Refresh token lifetime

# Optional Security Settings
MAX_LOGIN_ATTEMPTS=5                             # Failed login threshold
LOCKOUT_DURATION=15                              # Minutes to lock account
ALGORITHM="HS256"                                # JWT algorithm
DEBUG=false                                      # Disable in production

# Cache Configuration
REDIS_URL="redis://localhost:6379/0"             # Optional Redis cache
CACHE_TTL=3600                                   # Cache lifetime in seconds
```

### Security Recommendations

1. **Token Management**
   - Use strong secret keys (min 32 characters)
   - Enable short token expiration (30 minutes recommended)
   - Implement token rotation
   - Use secure cookie storage for tokens

2. **Rate Limiting Configuration**
   - Set appropriate attempt thresholds (default: 5)
   - Use sliding window rate limiting
   - Implement IP-based blocking
   - Configure adequate block duration

3. **Caching Strategy**
   - Enable Redis for distributed environments
   - Set appropriate TTL values
   - Implement cache invalidation
   - Handle cache failures gracefully

4. **Audit Configuration**
   - Enable comprehensive logging
   - Monitor authentication failures
   - Track permission violations
   - Configure log rotation
   - Sanitize sensitive data

## Authors and Maintainers
- **pAPI Team**
- **Eduardo Fírvida** (efirvida@gmail.com)

## Version History

### 1.0.0 (2025-06-05)
- Implemented rate limiting and brute force protection
- Added comprehensive audit logging system
- Improved caching with Redis support
- Enhanced security with token rotation
- Added detailed security documentation
- Fixed performance issues in user authentication
- Improved error handling and logging

### 0.1.0 (Initial Release)
- Basic authentication and authorization
- Role and group-based access control
- User management features
- Basic security features
