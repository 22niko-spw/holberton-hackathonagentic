# SPEC.md

## Problème

Dans une entreprise, chaque événement (arrivée d'un nouveau stagiaire/employé,
réunion, afterwork) déclenche une série d'actions manuelles et répétitives :
trouver un créneau commun, poser la réunion, prévenir les bonnes personnes par
mail. L'agent reçoit une intention en langage naturel, construit un plan
d'actions concrètes (vérifier les disponibilités, proposer un créneau,
rédiger et envoyer les mails), l'affiche pour validation humaine action par
action, puis exécute uniquement ce qui est approuvé. Chaque action est
journalisée et annulable.

## User stories

1. En tant que RH, je veux décrire l'arrivée d'un nouveau stagiaire/employé
   afin que l'agent planifie automatiquement les actions associées (accès,
   annonce, réunion d'intégration).
2. En tant qu'organisateur, je veux que l'agent trouve un créneau commun
   entre plusieurs employés afin de poser une réunion sans allers-retours
   manuels.
3. En tant qu'équipe, je veux être notifiée par mail des événements internes
   (arrivée, réunion, afterwork) afin de rester informée sans effort de
   communication manuel.

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

