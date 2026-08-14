# Datenmodell

## User

- `id`
- `username`
- `email`
- `password_hash`
- `salt`
- `xp`
- `level`
- `premium_status`
- `created_at`

## Course

Kurse liegen datengetrieben in `data/courses/*.json`.

- `id`
- `language`
- `title`
- `description`
- `free`
- `lessons[]`

## Lesson

- `id`
- `course_id`
- `title`
- `summary`
- `explanation`
- `demo`
- `task`
- `xp`
- `premium`
- `success_message`

## Task

Im MVP ist die Aufgabe Teil der Lektion. Spaeter kann sie in eine eigene Tabelle oder Collection ausgelagert werden.

- `id`
- `kind`
- `prompt`
- `steps[]`
- `checks[]`

## Progress

- `user_id`
- `lesson_id`
- `course_id`
- `completed_at`
- `xp_awarded`

## Badge

- `id`
- `name`
- `description`
- `icon`
- `rule`

## UserBadge

- `user_id`
- `badge_id`
- `awarded_at`

## Reward

- `id`
- `name`
- `type`
- `unlock_rule`

## Project

- `id`
- `user_id`
- `title`
- `description`
- `scratch_url`
- `is_public`
- `created_at`
- `updated_at`

## Subscription

Im MVP als Feld `premium_status`, spaeter eigene Tabelle:

- `id`
- `user_id`
- `provider`
- `provider_customer_id`
- `status`
- `current_period_end`

## AI Interaction / Usage Limits

- `id`
- `user_id`
- `lesson_id`
- `message`
- `response`
- `created_at`
- `safety_label`
