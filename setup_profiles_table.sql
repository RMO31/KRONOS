-- ═══════════════════════════════════════════════════════════════════════════
-- جدول الملفات الشخصية للمستخدمين — كرونوس
-- نفّذ هذا السكريبت في Supabase → SQL Editor مرة واحدة فقط
-- ═══════════════════════════════════════════════════════════════════════════

create table if not exists profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  username    text,
  email       text,
  avatar_url  text,
  country     text,
  birth_date  date,
  birth_place text,
  hobby       text,
  created_at  timestamptz default now()
);

-- تفعيل الحماية على مستوى الصفوف
alter table profiles enable row level security;

-- السماح بقراءة كل الملفات الشخصية (لعرض الأعضاء في الموقع العام)
drop policy if exists "profiles_public_read" on profiles;
create policy "profiles_public_read"
  on profiles for select
  using (true);

-- السماح للمستخدم بإنشاء ملفه الشخصي فقط (id يطابق هويته)
drop policy if exists "profiles_insert_own" on profiles;
create policy "profiles_insert_own"
  on profiles for insert
  with check (auth.uid() = id);

-- السماح للمستخدم بتعديل ملفه الشخصي فقط
drop policy if exists "profiles_update_own" on profiles;
create policy "profiles_update_own"
  on profiles for update
  using (auth.uid() = id);

-- ملاحظة: تأكد أن "Enable email confirmations" في
-- Supabase → Authentication → Providers → Email مُفعّل حسب رغبتك:
--   • مفعّل  → المستخدم يحتاج تأكيد البريد قبل أول دخول
--   • معطّل → الحساب يُفعَّل فوراً بعد التسجيل (المستخدم يدخل مباشرة لبطاقة الملف الشخصي)
