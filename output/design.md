# Bookend: design

*Book club, on your own time, and without the books you just don't want to read.*

The app should feel clean and bright, like a fresh page, with navy ink, real covers everywhere, and a little
movement (turning gears, drifting covers, a spinning globe). Color tells you **who you're talking to**: people
are blue, AI is coral.

## Color

Only the six reference colors are used, on a plain white page.

| Name | RGB | Where | Why |
|---|---|---|---|
| White | 255, 255, 255 | Page background and the full-width, translucent header | Clean and bright; the header blends into the page |
| Navy | 5, 18, 48 | Text, your own messages, primary buttons, the active tab, the globe | The "ink" |
| Cream | 255, 239, 174 | Cards (lightened), text on navy, city dots on the globe | The bright parts of the page |
| Pale blue | 165, 200, 209 | Everything about **people**: the "Chat w/ people" book, reader rooms, member chips | Calm and human |
| Coral | 244, 128, 103 | Everything about **AI**: the "Chat w/ us" book, AI rooms, the Book Companion | Warm but clearly different from the people color |
| Burnt orange | 187, 113, 37 | Discussion Host, star ratings, italic accents, the small gears | The Host is AI that sits *inside* a people room, so it gets its own warm color |
| Olive | 164, 149, 49 | Recommendation agent, "General knowledge" label | |

### One color per agent

Every AI message has a ✦ avatar and a tag in its agent's color, plus the word "AI".

| Agent | Color |
|---|---|
| Moderator | Deep red `#a8321e` (shield badge, hidden-message outline) |
| Matchmaker | Dark pale-blue `#3f7484` |
| Discussion Host | Burnt orange `#bb7125` |
| Book Companion | Coral `#d9634a` (darkened for white text) |
| Recommendation | Olive `#857a22` (darkened for white text) |

## Type

| Use | Font | Why |
|---|---|---|
| Logo letters, headings, speech bubbles | **Fraunces** (serif, with italic accents) | Bookish and warm |
| Body, chat, tables | **Inter** | Very readable at chat sizes |

Both are bundled with the app (`@fontsource`), so it looks the same offline.

## The logo

The **Bookend** artwork (provided by the project owner): seven cloth-bound hardcovers in the palette colors, the
word "Bookend" in a cream-and-olive serif across the spines, small gilt ornaments and rules. Its off-white
background was removed (`frontend/src/assets/bookend-logo.png`, transparent) so it sits on the white page. On the
home page it stands on a slim shelf between two pairs of **turning metal gears**, the bookends: trapezoid teeth,
brushed-metal shading, a beveled rim, spoke windows, and a screwed hub, in copper-coral (244,128,103) and
steel pale blue (165,200,209). The top bar shows the artwork alone.

## Welcome screen

Logged-out readers see the logo and tagline over two cards: **Create account / Log in** (one form with a toggle)
and **Try a demo reader** (pale blue, eight sample readers as one-click chips, and Booksy waiting at the bottom).
Signed in, the top bar shows your avatar, display name, a "Demo reader" tag for sample readers, and **Log out**
(or **Switch reader** for demo readers).

## Booksy

**Booksy** is the face of everything AI ("chat with us"): an orange tabby with round glasses and a blue-and-white
scarf, reading *Wondrous Tales*. Cut out of the provided illustration (`frontend/src/assets/booksy.png`) with the
background and stool removed. Booksy appears on the home page's AI card, in the "With us" group of the chat list,
in the banner of AI chats, beside every Booksy message, and in the "Talk with Booksy" choice after logging a book.

## Home page

1. **Masthead**: the option H logo and the tagline.
2. **Log a book**: a navy pill button. It opens search with **suggestions as you type** (English titles only),
   then the finish flow (date, stars, matching window) and the match result.
3. **Three side-by-side cards** (option A plus your rooms), with generous space above them:
   - **With people** (pale blue): an avatar stack of readers who just finished your latest book, "2 readers just
     finished *Project Hail Mary*", and **Join them**.
   - **With us · AI** (coral): Booksy, "Talk with Booksy, your AI reading companion", **Talk with Booksy** and
     **Find your next book**.
   - **Your rooms** (light gray): the reader rooms you've joined, each one click away ("Pick up where you left off").
   If you're already in the room for your latest book, the people card says **Open your room** instead of **Join them**.
4. **Your next book**: three picks the Recommendation agent writes in the background whenever you log a book.
5. **Your shelf**: your covers, centered, on a slim ledge, with your star ratings.
6. **Cover rail** (right edge): large covers drifting slowly upward; pauses on hover; click one to log it.

## Chats

- **Two groups** in the list: **👥 With readers · real people** (blue) and **✦ With AI · not a person** (coral).
- **A banner** at the top of every chat: "You're talking with real readers" (blue) or "You're talking with an AI,
  not a person" (coral). The chat's top edge and background tint match.
- **A globe** under the list: a navy globe turning slowly, with cream city dots and colored arcs flying between
  random cities, for "people who finished the same book, from anywhere in the world."
- Message bubbles match the home page: flat, rounded, with a small tail (navy for you, pale blue for other
  readers, tinted for each AI agent).
- Hidden messages are visible only to their sender, struck through, with a red dashed outline and the reason.
- Pending messages show "🛡 Checking…" while the Moderator works.
- AI messages don't show their cost (tokens and cost per agent are on Behind the scenes).

## Other tabs

- **What next?**: the Recommendation chat; picks are book cards with "✓ In the catalog".
- **Behind the scenes**: the agent hand-off diagram in three lanes, measured tokens and cost per agent, every
  agent run (click for its tool calls and answer), and the moderation log.
