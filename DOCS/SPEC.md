# SPEC.md

## Problème

Dans une entreprise, chaque arrivée, réunion ou événement interne déclenche
des tâches manuelles répétitives : trouver un créneau, poser la réunion,
prévenir les bonnes personnes par mail. Le RH perd du temps sur ces tâches
à faible valeur, et les oublis (une annonce non envoyée, une réunion non
posée) sont fréquents. Un agent qui prend en charge cette planification,
sous supervision humaine, doit libérer ce temps tout en gardant le contrôle
sur ce qui est réellement exécuté.

## User stories

1. En tant que RH, je veux décrire l'arrivée d'un nouveau stagiaire/employé
   afin que l'agent planifie automatiquement les actions associées (accès,
   annonce, réunion d'intégration).
2. En tant que RH, je veux que l'agent trouve un créneau commun entre
   plusieurs employés afin de poser une réunion sans allers-retours manuels.
3. En tant que RH, je veux que l'équipe soit notifiée par mail des
   événements internes (arrivée, réunion, afterwork) afin qu'elle reste
   informée sans effort de communication manuel de ma part.

## Hors scope

1. Pas d'intégration à de vraies API externes (Google Calendar, Gmail) —
   calendrier et mail mockés localement, assumé et documenté.
2. Pas de gestion multi-entreprises / multi-tenant.
3. Pas d'annulation en cascade d'un événement déjà créé (seulement la
   dernière action).
4. Pas de gestion des conflits de créneaux complexes (fuseaux horaires,
   récurrence, optimisation multi-critères) `find_common_slot` reste
   volontairement simple.
5. Pas d'authentification/gestion de rôles utilisateurs (un seul utilisateur
   RH pour le hackathon).
6. Pas de notification en temps réel (push, SMS) — mail (mocké) uniquement.

