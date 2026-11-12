# Database schema

Generated from the SQLAlchemy models. Migrations live in `backend/alembic/versions`.

## `api_request_logs`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER |  |
| `actor` | VARCHAR(80) | NOT NULL |
| `method` | VARCHAR(10) | NOT NULL |
| `path` | VARCHAR(300) | NOT NULL |
| `status` | INTEGER | NOT NULL |
| `ip` | VARCHAR(64) |  |
| `created_at` | DATETIME | NOT NULL |

## `audit_logs`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER |  |
| `actor_user_id` | INTEGER |  |
| `actor_label` | VARCHAR(200) |  |
| `action` | VARCHAR(80) | NOT NULL |
| `resource_type` | VARCHAR(40) |  |
| `resource_id` | VARCHAR(80) |  |
| `detail` | JSON |  |
| `ip` | VARCHAR(64) |  |
| `created_at` | DATETIME | NOT NULL |

## `organizations`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `name` | VARCHAR(160) | NOT NULL |
| `slug` | VARCHAR(80) | NOT NULL, UNIQUE |
| `plan` | VARCHAR(30) | NOT NULL |
| `industry` | VARCHAR(80) |  |
| `timezone` | VARCHAR(60) | NOT NULL |
| `settings` | JSON | NOT NULL |
| `active` | BOOLEAN | NOT NULL |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `permissions`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `key` | VARCHAR(80) | NOT NULL, UNIQUE |
| `description` | VARCHAR(200) | NOT NULL |

## `saml_assertions_seen`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `assertion_id` | VARCHAR(160) | NOT NULL, UNIQUE |
| `seen_at` | DATETIME | NOT NULL |

## `simulated_emails`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `to_email` | VARCHAR(200) | NOT NULL |
| `subject` | VARCHAR(300) | NOT NULL |
| `body` | TEXT | NOT NULL |
| `created_at` | DATETIME | NOT NULL |

## `test_cases`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `code` | VARCHAR(30) | NOT NULL, UNIQUE |
| `category` | VARCHAR(60) | NOT NULL |
| `title` | VARCHAR(240) | NOT NULL |
| `description` | TEXT | NOT NULL |
| `module` | VARCHAR(60) | NOT NULL |
| `preconditions` | TEXT | NOT NULL |
| `required_role` | VARCHAR(60) | NOT NULL |
| `objective` | TEXT | NOT NULL |
| `procedure` | TEXT | NOT NULL |
| `expected_secure` | TEXT | NOT NULL |
| `indicators` | TEXT | NOT NULL |
| `severity` | VARCHAR(20) | NOT NULL |
| `evidence` | TEXT | NOT NULL |
| `remediation` | TEXT | NOT NULL |
| `references` | JSON | NOT NULL |
| `auth_required` | BOOLEAN | NOT NULL |
| `api_type` | VARCHAR(20) | NOT NULL |
| `technology` | VARCHAR(40) | NOT NULL |
| `execution` | VARCHAR(20) | NOT NULL |
| `vuln_toggle` | VARCHAR(60) |  |
| `version` | INTEGER | NOT NULL |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `users`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `email` | VARCHAR(200) | NOT NULL, UNIQUE |
| `name` | VARCHAR(160) | NOT NULL |
| `password_hash` | VARCHAR(200) | NOT NULL |
| `mfa_enabled` | BOOLEAN | NOT NULL |
| `mfa_secret` | VARCHAR(64) |  |
| `active` | BOOLEAN | NOT NULL |
| `last_login` | DATETIME |  |
| `external_subject` | VARCHAR(200) |  |
| `avatar_color` | VARCHAR(12) | NOT NULL |
| `preferences` | JSON | NOT NULL |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `auth_sessions`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `sid` | VARCHAR(80) | NOT NULL, UNIQUE |
| `user_id` | INTEGER | FK → users.id |
| `org_id` | INTEGER |  |
| `stage` | VARCHAR(20) | NOT NULL |
| `method` | VARCHAR(20) | NOT NULL |
| `ip` | VARCHAR(64) |  |
| `user_agent` | VARCHAR(300) |  |
| `revoked` | BOOLEAN | NOT NULL |
| `created_at` | DATETIME | NOT NULL |
| `last_seen` | DATETIME | NOT NULL |
| `expires_at` | DATETIME |  |

## `integration_configs`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `kind` | VARCHAR(40) | NOT NULL |
| `name` | VARCHAR(160) | NOT NULL |
| `config` | JSON | NOT NULL |
| `enabled` | BOOLEAN | NOT NULL |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `oauth_clients`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `client_id` | VARCHAR(80) | NOT NULL, UNIQUE |
| `client_secret_hash` | VARCHAR(200) |  |
| `client_secret_plain` | VARCHAR(80) |  |
| `name` | VARCHAR(160) | NOT NULL |
| `redirect_uris` | JSON | NOT NULL |
| `grant_types` | JSON | NOT NULL |
| `scopes` | JSON | NOT NULL |
| `public` | BOOLEAN | NOT NULL |
| `require_pkce` | BOOLEAN | NOT NULL |
| `active` | BOOLEAN | NOT NULL |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `oauth_codes`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `code` | VARCHAR(120) | NOT NULL, UNIQUE |
| `client_id` | VARCHAR(80) | NOT NULL |
| `user_id` | INTEGER | NOT NULL, FK → users.id |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `scope` | VARCHAR(400) | NOT NULL |
| `redirect_uri` | VARCHAR(500) | NOT NULL |
| `code_challenge` | VARCHAR(200) |  |
| `code_challenge_method` | VARCHAR(10) |  |
| `nonce` | VARCHAR(200) |  |
| `used` | BOOLEAN | NOT NULL |
| `expires_at` | DATETIME | NOT NULL |

## `oauth_tokens`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `access_hash` | VARCHAR(128) | NOT NULL, UNIQUE |
| `refresh_hash` | VARCHAR(128) |  |
| `client_id` | VARCHAR(80) | NOT NULL |
| `user_id` | INTEGER | FK → users.id |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `scope` | VARCHAR(400) | NOT NULL |
| `family` | VARCHAR(60) |  |
| `expires_at` | DATETIME | NOT NULL |
| `refresh_expires_at` | DATETIME |  |
| `revoked` | BOOLEAN | NOT NULL |
| `created_at` | DATETIME | NOT NULL |

## `otp_challenges`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `challenge_id` | VARCHAR(60) | NOT NULL, UNIQUE |
| `user_id` | INTEGER | NOT NULL, FK → users.id |
| `code_hash` | VARCHAR(128) | NOT NULL |
| `attempts` | INTEGER | NOT NULL |
| `consumed` | BOOLEAN | NOT NULL |
| `expires_at` | DATETIME | NOT NULL |

## `password_resets`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `user_id` | INTEGER | NOT NULL, FK → users.id |
| `token` | VARCHAR(80) | NOT NULL, UNIQUE |
| `used` | BOOLEAN | NOT NULL |
| `expires_at` | DATETIME | NOT NULL |

## `roles`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | FK → organizations.id |
| `key` | VARCHAR(60) | NOT NULL |
| `name` | VARCHAR(100) | NOT NULL |
| `description` | VARCHAR(300) | NOT NULL |
| `permissions` | JSON | NOT NULL |
| `system` | BOOLEAN | NOT NULL |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `saml_configs`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | NOT NULL, UNIQUE, FK → organizations.id |
| `enabled` | BOOLEAN | NOT NULL |
| `idp_entity_id` | VARCHAR(300) | NOT NULL |
| `sso_url` | VARCHAR(500) | NOT NULL |
| `slo_url` | VARCHAR(500) |  |
| `x509_cert` | TEXT | NOT NULL |
| `sp_entity_id` | VARCHAR(300) | NOT NULL |
| `acs_url` | VARCHAR(500) | NOT NULL |
| `jit_provisioning` | BOOLEAN | NOT NULL |
| `default_role_key` | VARCHAR(60) | NOT NULL |
| `attribute_map` | JSON | NOT NULL |
| `require_signed_assertions` | BOOLEAN | NOT NULL |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `sso_sessions`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `request_id` | VARCHAR(80) | NOT NULL, UNIQUE |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `kind` | VARCHAR(10) | NOT NULL |
| `state` | VARCHAR(200) |  |
| `nonce` | VARCHAR(200) |  |
| `user_id` | INTEGER | FK → users.id |
| `name_id` | VARCHAR(300) |  |
| `session_index` | VARCHAR(120) |  |
| `status` | VARCHAR(12) | NOT NULL |
| `created_at` | DATETIME | NOT NULL |
| `ended_at` | DATETIME |  |

## `teams`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `name` | VARCHAR(120) | NOT NULL |
| `department` | VARCHAR(100) |  |
| `manager_id` | INTEGER | FK → memberships.id |
| `description` | VARCHAR(300) |  |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `test_case_versions`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `test_case_id` | INTEGER | NOT NULL, FK → test_cases.id |
| `version` | INTEGER | NOT NULL |
| `snapshot` | JSON | NOT NULL |
| `created_at` | DATETIME | NOT NULL |

## `webhooks`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `url` | VARCHAR(500) | NOT NULL |
| `events` | JSON | NOT NULL |
| `secret` | VARCHAR(80) |  |
| `active` | BOOLEAN | NOT NULL |
| `last_status` | VARCHAR(300) |  |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `memberships`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `user_id` | INTEGER | NOT NULL, FK → users.id |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `role_id` | INTEGER | NOT NULL, FK → roles.id |
| `team_id` | INTEGER | FK → teams.id |
| `manager_id` | INTEGER | FK → memberships.id |
| `title` | VARCHAR(120) |  |
| `department` | VARCHAR(100) |  |
| `phone` | VARCHAR(40) |  |
| `salary` | FLOAT |  |
| `internal_notes` | TEXT |  |
| `status` | VARCHAR(20) | NOT NULL |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `activities`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `entity_type` | VARCHAR(30) | NOT NULL |
| `entity_id` | INTEGER | NOT NULL |
| `kind` | VARCHAR(30) | NOT NULL |
| `subject` | VARCHAR(200) |  |
| `body` | TEXT |  |
| `actor_id` | INTEGER | FK → memberships.id |
| `created_at` | DATETIME | NOT NULL |

## `api_clients`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `name` | VARCHAR(160) | NOT NULL |
| `description` | VARCHAR(300) |  |
| `scopes` | JSON | NOT NULL |
| `owner_id` | INTEGER | FK → memberships.id |
| `active` | BOOLEAN | NOT NULL |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `customers`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `name` | VARCHAR(200) | NOT NULL |
| `email` | VARCHAR(200) |  |
| `phone` | VARCHAR(40) |  |
| `industry` | VARCHAR(80) |  |
| `company` | VARCHAR(200) |  |
| `website` | VARCHAR(200) |  |
| `address` | VARCHAR(300) |  |
| `status` | VARCHAR(20) | NOT NULL |
| `tier` | VARCHAR(20) | NOT NULL |
| `owner_id` | INTEGER | FK → memberships.id |
| `notes` | TEXT |  |
| `internal_notes` | TEXT |  |
| `credit_limit` | FLOAT |  |
| `tax_id` | VARCHAR(40) |  |
| `deleted_at` | DATETIME |  |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `notifications`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `membership_id` | INTEGER | FK → memberships.id |
| `title` | VARCHAR(200) | NOT NULL |
| `body` | VARCHAR(400) |  |
| `link` | VARCHAR(200) |  |
| `read` | BOOLEAN | NOT NULL |
| `created_at` | DATETIME | NOT NULL |

## `role_assignments`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `membership_id` | INTEGER | NOT NULL, FK → memberships.id |
| `role_id` | INTEGER | NOT NULL, FK → roles.id |
| `granted_by` | INTEGER | FK → users.id |
| `created_at` | DATETIME | NOT NULL |

## `api_keys`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `client_id` | INTEGER | NOT NULL, FK → api_clients.id |
| `prefix` | VARCHAR(16) | NOT NULL |
| `key_hash` | VARCHAR(128) | NOT NULL |
| `plaintext` | VARCHAR(80) |  |
| `scopes` | JSON | NOT NULL |
| `expires_at` | DATETIME |  |
| `last_used_at` | DATETIME |  |
| `revoked` | BOOLEAN | NOT NULL |
| `created_at` | DATETIME | NOT NULL |

## `customer_contacts`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `customer_id` | INTEGER | NOT NULL, FK → customers.id |
| `name` | VARCHAR(160) | NOT NULL |
| `email` | VARCHAR(200) |  |
| `phone` | VARCHAR(40) |  |
| `title` | VARCHAR(100) |  |
| `primary` | BOOLEAN | NOT NULL |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `leads`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `name` | VARCHAR(160) | NOT NULL |
| `email` | VARCHAR(200) |  |
| `phone` | VARCHAR(40) |  |
| `company` | VARCHAR(200) |  |
| `source` | VARCHAR(40) | NOT NULL |
| `status` | VARCHAR(20) | NOT NULL |
| `qualification` | VARCHAR(20) |  |
| `score` | INTEGER | NOT NULL |
| `estimated_value` | FLOAT |  |
| `owner_id` | INTEGER | FK → memberships.id |
| `created_by` | INTEGER | FK → memberships.id |
| `converted_customer_id` | INTEGER | FK → customers.id |
| `converted_at` | DATETIME |  |
| `notes` | TEXT |  |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `tickets`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `customer_id` | INTEGER | FK → customers.id |
| `subject` | VARCHAR(240) | NOT NULL |
| `description` | TEXT |  |
| `priority` | VARCHAR(20) | NOT NULL |
| `status` | VARCHAR(20) | NOT NULL |
| `assignee_id` | INTEGER | FK → memberships.id |
| `created_by` | INTEGER | FK → memberships.id |
| `escalated` | BOOLEAN | NOT NULL |
| `escalated_to` | INTEGER | FK → memberships.id |
| `resolved_at` | DATETIME |  |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `opportunities`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `customer_id` | INTEGER | FK → customers.id |
| `lead_id` | INTEGER | FK → leads.id |
| `name` | VARCHAR(200) | NOT NULL |
| `amount` | FLOAT | NOT NULL |
| `discount_pct` | FLOAT | NOT NULL |
| `stage` | VARCHAR(30) | NOT NULL |
| `probability` | INTEGER | NOT NULL |
| `expected_close` | DATETIME |  |
| `owner_id` | INTEGER | FK → memberships.id |
| `approval_status` | VARCHAR(20) | NOT NULL |
| `approved_by` | INTEGER | FK → memberships.id |
| `closed_at` | DATETIME |  |
| `notes` | TEXT |  |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `documents`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `name` | VARCHAR(240) | NOT NULL |
| `kind` | VARCHAR(20) | NOT NULL |
| `visibility` | VARCHAR(20) | NOT NULL |
| `owner_id` | INTEGER | FK → memberships.id |
| `customer_id` | INTEGER | FK → customers.id |
| `opportunity_id` | INTEGER | FK → opportunities.id |
| `current_version` | INTEGER | NOT NULL |
| `status` | VARCHAR(20) | NOT NULL |
| `deleted_at` | DATETIME |  |
| `created_at` | DATETIME | NOT NULL |
| `updated_at` | DATETIME | NOT NULL |

## `document_permissions`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `document_id` | INTEGER | NOT NULL, FK → documents.id |
| `membership_id` | INTEGER | NOT NULL, FK → memberships.id |
| `level` | VARCHAR(10) | NOT NULL |
| `granted_by` | INTEGER | FK → memberships.id |

## `document_versions`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `document_id` | INTEGER | NOT NULL, FK → documents.id |
| `version` | INTEGER | NOT NULL |
| `original_name` | VARCHAR(300) | NOT NULL |
| `stored_name` | VARCHAR(300) | NOT NULL |
| `content_type` | VARCHAR(120) | NOT NULL |
| `size` | INTEGER | NOT NULL |
| `uploaded_by` | INTEGER | FK → memberships.id |
| `created_at` | DATETIME | NOT NULL |

## `ticket_comments`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PK |
| `org_id` | INTEGER | NOT NULL, FK → organizations.id |
| `ticket_id` | INTEGER | NOT NULL, FK → tickets.id |
| `author_id` | INTEGER | FK → memberships.id |
| `body` | TEXT | NOT NULL |
| `internal` | BOOLEAN | NOT NULL |
| `document_id` | INTEGER | FK → documents.id |
| `created_at` | DATETIME | NOT NULL |
