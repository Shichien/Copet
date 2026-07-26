# Interaction Animation Rows

The interaction atlas is separate from the official Codex v2 atlas. It uses 8 columns, 12 rows, and `192x208` transparent cells. Its exact size is `1536x2496`.

| Row | State | Frames | Loop | Purpose |
| ---: | --- | ---: | --- | --- |
| 0 | feeding | 8 | no | Receive food, eat, swallow, and settle. |
| 1 | petting | 6 | yes | React to a hand or pointer stroking the pet. |
| 2 | bathing | 8 | no | Wash, shake off, and return clean. |
| 3 | playing | 8 | yes | Play with the pet's established toy or body language. |
| 4 | sleeping | 6 | yes | Settle into a quiet breathing sleep. |
| 5 | waking | 4 | no | Wake, stretch, and return to attention. |
| 6 | hungry | 6 | yes | Ask for food through body language. |
| 7 | dirty | 6 | yes | Show discomfort and need for cleaning. |
| 8 | sick | 8 | yes | Show low health without graphic distress. |
| 9 | happy | 6 | yes | Show a calm positive reaction. |
| 10 | celebrate | 8 | no | Celebrate a milestone or task reward. |
| 11 | refuse | 4 | no | Decline an invalid or unavailable action. |

Unused cells after the final frame in each row must be fully transparent.

## Motion Requirements

- `feeding`: The food must remain attached to the pet or held inside its silhouette. Do not draw a floating inventory item.
- `petting`: Show the reaction through head, ears, face, or body. Do not draw a detached hand; the runtime supplies the pointer interaction.
- `bathing`: Use attached opaque foam or droplets only. No translucent scenery or floor puddles.
- `playing`: Use an existing identity prop when available. Otherwise use body movement without inventing a detached toy.
- `sleeping`: Stay low-distraction, keep the base stable, and connect the final frame to the first.
- `waking`: Start from the sleeping pose and end near official idle.
- `hungry`, `dirty`, and `sick`: Remain readable without text, status icons, or interface symbols.
- `happy`: Keep this calmer than `celebrate` so automatic mood feedback is not distracting.
- `celebrate`: Use a clear full-body action without detached confetti or particles.
- `refuse`: Use a brief head or body gesture without text, crosses, or warning icons.
