---
name: ui-design-contract
description: Design UI journeys, screens, states and component contracts before implementation. Use when a story adds or changes user-facing screens; pair with ux-design-contract and a11y-contract for review.
---

# ui-design-contract

## Apply when
A story changes what the user sees or does.

## Method
1. Start from the story's journeys and acceptance criteria; read the existing UI and design tokens/components first and reuse them.
2. Specify per screen: purpose, layout hierarchy, every state (empty, loading, error, success, permission-denied, offline), copy, and primary/secondary actions.
3. Define reusable component contracts (props/inputs, variants, events) and responsive behavior at phone and desktop widths.
4. State accessibility behavior: focus order, labels, contrast, touch targets, reduced motion.
5. Mark open design questions with an owner; do not decide product behavior silently.

## Required output
`docs/sdlc/ui-spec.md` per the template; journey list; component inventory; open questions.

## Do not
Invent a new design system when one exists; leave states unspecified; replace the later UX and accessibility review.
