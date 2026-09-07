-- Additional cedar customers.
--
-- Search pagination cannot be tested against three rows: any page size looks correct when the
-- result set is smaller than the cap. These thirty give the search tool a set large enough that
-- the policy obligation (max_results = 25) is observable, and that a second page exists.
--
-- Every surname contains "ar", so a two-character query matches all of them.

BEGIN;

INSERT INTO app.customers (id, organization_id, external_ref, full_name, email, assigned_team, sensitivity) VALUES
  ('c0000001-0000-0000-0000-000000000010', '11111111-1111-1111-1111-111111111111',
   'CUS-4010', 'Ana Parker', 'ana.parker@example.invalid', 'team-south', 'normal'),
  ('c0000001-0000-0000-0000-000000000011', '11111111-1111-1111-1111-111111111111',
   'CUS-4011', 'Noor Marsh', 'noor.marsh@example.invalid', 'team-north', 'normal'),
  ('c0000001-0000-0000-0000-000000000012', '11111111-1111-1111-1111-111111111111',
   'CUS-4012', 'Ivo Carter', 'ivo.carter@example.invalid', 'team-south', 'normal'),
  ('c0000001-0000-0000-0000-000000000013', '11111111-1111-1111-1111-111111111111',
   'CUS-4013', 'Lena Harper', 'lena.harper@example.invalid', 'team-north', 'normal'),
  ('c0000001-0000-0000-0000-000000000014', '11111111-1111-1111-1111-111111111111',
   'CUS-4014', 'Omar Barnes', 'omar.barnes@example.invalid', 'team-south', 'normal'),
  ('c0000001-0000-0000-0000-000000000015', '11111111-1111-1111-1111-111111111111',
   'CUS-4015', 'Sofia Clark', 'sofia.clark@example.invalid', 'team-north', 'normal'),
  ('c0000001-0000-0000-0000-000000000016', '11111111-1111-1111-1111-111111111111',
   'CUS-4016', 'Petr Stewart', 'petr.stewart@example.invalid', 'team-south', 'normal'),
  ('c0000001-0000-0000-0000-000000000017', '11111111-1111-1111-1111-111111111111',
   'CUS-4017', 'Mira Garcia', 'mira.garcia@example.invalid', 'team-north', 'normal'),
  ('c0000001-0000-0000-0000-000000000018', '11111111-1111-1111-1111-111111111111',
   'CUS-4018', 'Elias Marquez', 'elias.marquez@example.invalid', 'team-south', 'normal'),
  ('c0000001-0000-0000-0000-000000000019', '11111111-1111-1111-1111-111111111111',
   'CUS-4019', 'Ruth Sharma', 'ruth.sharma@example.invalid', 'team-north', 'normal'),
  ('c0000001-0000-0000-0000-000000000020', '11111111-1111-1111-1111-111111111111',
   'CUS-4020', 'Kwame Aranda', 'kwame.aranda@example.invalid', 'team-south', 'normal'),
  ('c0000001-0000-0000-0000-000000000021', '11111111-1111-1111-1111-111111111111',
   'CUS-4021', 'Ines Farah', 'ines.farah@example.invalid', 'team-north', 'normal'),
  ('c0000001-0000-0000-0000-000000000022', '11111111-1111-1111-1111-111111111111',
   'CUS-4022', 'Tariq Karim', 'tariq.karim@example.invalid', 'team-south', 'normal'),
  ('c0000001-0000-0000-0000-000000000023', '11111111-1111-1111-1111-111111111111',
   'CUS-4023', 'Vera Barros', 'vera.barros@example.invalid', 'team-north', 'normal'),
  ('c0000001-0000-0000-0000-000000000024', '11111111-1111-1111-1111-111111111111',
   'CUS-4024', 'Hugo Marino', 'hugo.marino@example.invalid', 'team-south', 'normal'),
  ('c0000001-0000-0000-0000-000000000025', '11111111-1111-1111-1111-111111111111',
   'CUS-4025', 'Nadia Arnold', 'nadia.arnold@example.invalid', 'team-north', 'normal'),
  ('c0000001-0000-0000-0000-000000000026', '11111111-1111-1111-1111-111111111111',
   'CUS-4026', 'Emil Carver', 'emil.carver@example.invalid', 'team-south', 'normal'),
  ('c0000001-0000-0000-0000-000000000027', '11111111-1111-1111-1111-111111111111',
   'CUS-4027', 'Sara Hartley', 'sara.hartley@example.invalid', 'team-north', 'normal'),
  ('c0000001-0000-0000-0000-000000000028', '11111111-1111-1111-1111-111111111111',
   'CUS-4028', 'Dario Larkin', 'dario.larkin@example.invalid', 'team-south', 'normal'),
  ('c0000001-0000-0000-0000-000000000029', '11111111-1111-1111-1111-111111111111',
   'CUS-4029', 'Leah Marlow', 'leah.marlow@example.invalid', 'team-north', 'normal'),
  ('c0000001-0000-0000-0000-000000000030', '11111111-1111-1111-1111-111111111111',
   'CUS-4030', 'Yusuf Narayan', 'yusuf.narayan@example.invalid', 'team-south', 'normal'),
  ('c0000001-0000-0000-0000-000000000031', '11111111-1111-1111-1111-111111111111',
   'CUS-4031', 'Clara Parry', 'clara.parry@example.invalid', 'team-north', 'normal'),
  ('c0000001-0000-0000-0000-000000000032', '11111111-1111-1111-1111-111111111111',
   'CUS-4032', 'Mateo Sarkar', 'mateo.sarkar@example.invalid', 'team-south', 'normal'),
  ('c0000001-0000-0000-0000-000000000033', '11111111-1111-1111-1111-111111111111',
   'CUS-4033', 'Ilse Tarrant', 'ilse.tarrant@example.invalid', 'team-north', 'normal'),
  ('c0000001-0000-0000-0000-000000000034', '11111111-1111-1111-1111-111111111111',
   'CUS-4034', 'Rania Varga', 'rania.varga@example.invalid', 'team-south', 'normal'),
  ('c0000001-0000-0000-0000-000000000035', '11111111-1111-1111-1111-111111111111',
   'CUS-4035', 'Bo Warner', 'bo.warner@example.invalid', 'team-north', 'normal'),
  ('c0000001-0000-0000-0000-000000000036', '11111111-1111-1111-1111-111111111111',
   'CUS-4036', 'Signe Amara', 'signe.amara@example.invalid', 'team-south', 'normal'),
  ('c0000001-0000-0000-0000-000000000037', '11111111-1111-1111-1111-111111111111',
   'CUS-4037', 'Faisal Bardot', 'faisal.bardot@example.invalid', 'team-north', 'normal'),
  ('c0000001-0000-0000-0000-000000000038', '11111111-1111-1111-1111-111111111111',
   'CUS-4038', 'Greta Cardenas', 'greta.cardenas@example.invalid', 'team-south', 'normal'),
  ('c0000001-0000-0000-0000-000000000039', '11111111-1111-1111-1111-111111111111',
   'CUS-4039', 'Nikos Delgardo', 'nikos.delgardo@example.invalid', 'team-north', 'normal')
ON CONFLICT (organization_id, external_ref) DO UPDATE SET full_name = EXCLUDED.full_name;

COMMIT;
