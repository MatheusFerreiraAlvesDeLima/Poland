-- Table of available plans
CREATE TABLE IF NOT EXISTS plans (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    features JSONB NOT NULL,
    price NUMERIC(10,2) NOT NULL,
    stripe_price_id TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table of companies (tenants)
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    country TEXT NOT NULL,
    industry TEXT NOT NULL,
    stripe_customer_id TEXT,
    date_registered TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    plan_id INTEGER REFERENCES plans(id),
    max_projects INT DEFAULT 3,
    max_users INT DEFAULT 1,
    max_storage VARCHAR(20) DEFAULT '100MB',
    current_projects INT DEFAULT 0,
    current_users INT DEFAULT 1
);

-- Table of subscriptions (full version)
CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    plan_id INTEGER NOT NULL REFERENCES plans(id),
    stripe_subscription_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('active', 'trialing', 'past_due', 'canceled', 'unpaid')),
    current_period_start TIMESTAMP NOT NULL,
    current_period_end TIMESTAMP NOT NULL,
    cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
    last_invoice_id TEXT,
    last_invoice_url TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    renewal_date DATE NOT NULL DEFAULT (CURRENT_DATE + INTERVAL '1 month')
);

-- Table of users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    phone TEXT,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    verification_token TEXT,
    verification_token_expiry TIMESTAMP,
    reset_token TEXT,
    reset_token_expiry TIMESTAMP,
    last_login TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table of projects
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table of tasks
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    due_date DATE,
    assigned_user_id INTEGER REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'Not Started',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table of income
CREATE TABLE IF NOT EXISTS income (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    date DATE NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    invoice_id TEXT,
    invoice_link TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table of expenses
CREATE TABLE IF NOT EXISTS expenses (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    date DATE NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    invoice_id TEXT,
    invoice_link TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table of general company-level expenses
CREATE TABLE IF NOT EXISTS general_expenses (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    type VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table of audit logs
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    company_id INTEGER REFERENCES companies(id),
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id INTEGER,
    ip_address TEXT,
    user_agent TEXT,
    details JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table of payments
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    amount NUMERIC(10,2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    invoice_id TEXT NOT NULL UNIQUE,
    invoice_url TEXT NOT NULL,
    payment_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table of plan change history
CREATE TABLE IF NOT EXISTS plan_changes (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    old_plan_id INTEGER REFERENCES plans(id),
    new_plan_id INTEGER NOT NULL REFERENCES plans(id),
    change_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    stripe_event_id TEXT
);

-- Indexes for optimization
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_company ON users(company_id);
CREATE INDEX IF NOT EXISTS idx_companies_email ON companies(email);
CREATE INDEX IF NOT EXISTS idx_subscriptions_company ON subscriptions(company_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_period ON subscriptions(current_period_end);
CREATE INDEX IF NOT EXISTS idx_projects_company ON projects(company_id);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_income_project ON income(project_id);
CREATE INDEX IF NOT EXISTS idx_expenses_project ON expenses(project_id);
CREATE INDEX IF NOT EXISTS idx_plan_changes_company ON plan_changes(company_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_email ON users(email);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_company_email ON companies(email);

-- Trigger to update project count in companies table
CREATE OR REPLACE FUNCTION update_project_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE companies
        SET current_projects = current_projects + 1
        WHERE id = NEW.company_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE companies
        SET current_projects = current_projects - 1
        WHERE id = OLD.company_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'project_count_trigger'
    ) THEN
        CREATE TRIGGER project_count_trigger
        AFTER INSERT OR DELETE ON projects
        FOR EACH ROW
        EXECUTE FUNCTION update_project_count();
    END IF;
END;
$$;

-- Trigger to update user count in companies table
CREATE OR REPLACE FUNCTION update_user_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE companies
        SET current_users = current_users + 1
        WHERE id = NEW.company_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE companies
        SET current_users = current_users - 1
        WHERE id = OLD.company_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'user_count_trigger'
    ) THEN
        CREATE TRIGGER user_count_trigger
        AFTER INSERT OR DELETE ON users
        FOR EACH ROW
        EXECUTE FUNCTION update_user_count();
    END IF;
END;
$$;

-- Trigger to auto-update the updated_at column
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    tbl text;
BEGIN
    FOR tbl IN
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name IN (
            'plans', 'companies', 'subscriptions', 'users', 
            'projects', 'tasks', 'income', 'expenses', 
            'general_expenses', 'audit_log', 'payments', 'plan_changes'
        )
    LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = format('update_%s_updated_at', tbl)
        ) THEN
            EXECUTE format('
                CREATE TRIGGER update_%s_updated_at
                BEFORE UPDATE ON %s
                FOR EACH ROW EXECUTE FUNCTION update_modified_column()',
                tbl, tbl);
        END IF;
    END LOOP;
END;
$$;

-- Insert or update default plans
INSERT INTO plans (name, description, features, price, stripe_price_id) 
VALUES 
('Free', 'Initial free plan', 
 '{"max_projects": 3, "max_users": 1, "max_storage": "100MB"}', 
 0.00, 'price_1Rap7kGK1tkBcsruKBjT5y7c'),
('Basic', 'Basic plan for small teams', 
 '{"max_projects": 10, "max_users": 5, "max_storage": "1GB"}', 
 99.00, 'price_1Rap86GK1tkBcsruzIHX09Ek'),
('Professional', 'Comprehensive plan for businesses', 
 '{"max_projects": 50, "max_users": 20, "max_storage": "10GB"}', 
 199.00, 'price_1RapH6GK1tkBcsruge7gNO4m'),
('Enterprise', 'Custom enterprise solution', 
 '{"max_projects": -1, "max_users": -1, "max_storage": "100GB"}', 
 499.00, 'price_1RapHbGK1tkBcsru3vvG2fbZ')
ON CONFLICT (name) DO UPDATE SET
    description = EXCLUDED.description,
    features = EXCLUDED.features,
    price = EXCLUDED.price,
    stripe_price_id = EXCLUDED.stripe_price_id;

-- Insert demo company (ignores if already exists)
INSERT INTO companies (name, email, country, industry, is_active, plan_id)
VALUES ('Demo Company', 'demo@company.com', 'BR', 'Technology', TRUE, 
        (SELECT id FROM plans WHERE name = 'Professional'))
ON CONFLICT (email) DO NOTHING;

-- Insert admin user for demo company (password: 'password123')
INSERT INTO users (first_name, last_name, email, password, company_id, is_admin, email_verified)
VALUES ('Admin', 'Demo', 'admin@demo.com', 
        '$2a$12$K9/IcF0Yd/w7WJN1d6S0.OUg4DnQ.F0n3O3V7nR7zX1bV8JkL8ZZG',
        (SELECT id FROM companies WHERE email = 'demo@company.com'), 
        TRUE, TRUE)
ON CONFLICT (email) DO NOTHING;
