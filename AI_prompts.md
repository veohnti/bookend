# Problem 1: Plan the final project

## Initial prompt (verbatim)

Let's start building this final project! Before we start, make sure you read the conversation we had in the Ideation Phase chat.
How would you recommend we start? Also given these instructions: https://zlisto.github.io/mgt_409_fa26/project_requirements.html

## Summarized follow-up prompts

_No follow-up prompts yet._

_What was missing in the original prompt: Nothing identified yet; follow-up prompts have not been provided._

# Problem 2: Build the app

## Initial prompt (verbatim)

I'd like to start and ideally finish it all today! But yes, sounds like a good plan. I would like you to also look at how we've been building on other projects (such as having a harness, md files, etc...). I'd like this project to be similar to the work we finished in HW6, HW5, and HW4. With that in mind, let's start! Do we need to share our prompts log for this assignment (based on the html page you looked at earlier?)

## Summarized follow-up prompts

### Follow-up 1

Pause before finalizing the report and slides: the user wants to suggest edits to the web app first, and the
report should be built after those changes.

**What was missing in the original prompt:** "Finish it all today" didn't say the user wanted to review and
edit the app's look before the report and slides were produced from it.

### Follow-up 2

Redesign the web app from a hand-drawn sketch: rename it **Bookend** (tagline: "Book club, on your own time,
and without the books you just don't want to read"); a logo where each letter of BOOKEND is a different-colored
book on a shelf, with gears as the bookends; a home page with Log a book, "Chat w/ people" and "Chat w/ us"
books with speech bubbles, "Your next book" that updates from the last logged book, Your shelf, and a scrolling
panel of book covers for movement. Use the palette (164,149,49 · 165,200,209 · 187,113,37 · 255,239,174 ·
244,128,103 · 5,18,48) on an old-book-page background (about 214,187,135). Make it clearer in Chats when you're
talking with the Book Companion versus real people, and add a globe graphic with lines between random places.

**What was missing in the original prompt:** The original asked for the build to follow the HW4–HW6 pattern but
gave no direction on name, branding, colors, or page layout, and didn't flag that AI vs. human chats needed to
be visually distinct.

### Follow-up 3

Design revisions: make the background much whiter and drop the 214,187,135 page color (use only the six palette
colors); make the scrolling covers on the right bigger; center the cover images in "Your next book"; make the
books spelling BOOKEND look like real books; color the moving gears coral (244,128,103) and pale blue
(165,200,209); make the header span the full page and blend with the background; and make the speech bubbles
look natural, like a reference image of flat, pill-shaped chat bubbles with small pointed tails (not its blue colors).

**What was missing in the original prompt:** Follow-up 2's old-page background and stylized spines didn't match
the look the user wanted; the bubble style and header treatment hadn't been specified.

### Follow-up 4

Logo and home-page polish: remove the dark background behind the logo letters so every letter blends into its
spine (like the E); fix the "Talk to the Book Companion" button, which looked like something was behind it;
make the logo books look even more realistic, then more elegant and less childish; center the shelf. Also asked
what the "Daily AI budget reached" message means.

**What was missing in the original prompt:** Follow-up 3 asked for "more realistic" books without saying the
user wanted a restrained, elegant style; the button issue was a bug (a decorative class name clashed with the
button's class), not a missing requirement.

### Follow-up 5

Use a provided "Bookend" book-spine image as the logo; make the gears look more realistic; make the background
white; center the books on Your shelf; show suggestions while typing the book to log; and show English titles
only (a logged Murakami book produced recommendations with Japanese titles).

**What was missing in the original prompt:** The search requirements never said results must be English, and
Open Library stores some translated works under their original-language title; type-ahead wasn't requested
before.

### Follow-up 6

Use logo option H (book-spine bars beside a serif "Bookend") and make the page a little more modern; hide the
cost shown under each AI message; fix the doubled message that appears while the Moderator checks it; add more
space between Log a book, Chat with people, and Chat with us; show continents on the globe; rename "What next?"
to "Your Next Book" and "Chats" to "Let's chat about it"; and propose a few designs for the chat-with sections
to choose from.

**What was missing in the original prompt:** Earlier rounds didn't settle the logo or how modern the page
should feel; the doubled message was a bug (the Moderator-check preview and the saved message could show at
the same time), not a missing requirement.

### Follow-up 7

Use option A (two side-by-side cards) for chatting with people and with us. Rename the AI companion "Booksy,
your AI reading companion" ("Talk with Booksy, your AI reading companion"), and use the cat from a provided
illustration (with his glasses and book, without the background) as Booksy's image wherever the app refers to
chatting with us.

**What was missing in the original prompt:** The AI companion had no name, personality, or image; the user
wanted a friendly character to make the AI side feel distinct from talking with people.

### Follow-up 8

Asked whether the demo reader switcher should become real sign-up and log-in (as in an earlier homework) or
stays for graders; asked to make the agents clearer in the Behind the scenes diagram with easier-to-follow
arrows; asked whether the app can be hosted publicly for free on Render; and asked whether two different people
who log the same book can talk to each other.

**What was missing in the original prompt:** The original didn't decide between a demo user switcher and real
accounts, or between running locally and hosting online, which also decides whether strangers can actually
reach each other.

### Follow-up 9

Add real sign-up and log-in, keep a "Try a demo reader" option for graders, and don't host on Render for now
(maybe after grades post).

**What was missing in the original prompt:** The build used a demo user switcher; the user wanted real accounts
like an earlier homework while keeping one-click demo access for grading.

# Problem 3: Report, slides, and other deliverables

## Initial prompt (verbatim)

Great, now we can start on the report and all the other deliverables. In terms of next steps for me it is: once graded, i will publish it to render using the $7/month (check that this is the case), turn it into an app, then I'm going to test run it with 10-20 users to get feedback and iterate on it, then I will advertise it on Yale's campus to try to get real users on the app.
When it comes to the problem and who has it, this is how I think about it: "Have you ever finished a book, and wondered what now? Your partner or friends are reading a completely different book. But you want to talk to someone about it? Join BookEnd! You can talk about your book with other people who just finished it and also just have their thoughts ready to go!" or " Have you been invited to bookclub before and while there is one book on the roster you like, everything else is booty? So you don't join the bookclub? The solution is Bookend! Your own BookClub! where you build a community". Or "you just finished a book, and have to ask your 200 friends (you are popular) if they read it so you could maybe talk to them about it? But maybe someone read it 2 years ago and doesn't even remember teh names of the people? Join BookEnd!"

* now please write the report and the slides and use the websites feel to help design the slides and all that.
* Read the instructions again on https://zlisto.github.io/mgt_409_fa26/project_requirements.html to make sure we hit all of the questions being asked

## Summarized follow-up prompts

### Follow-up 1

Make it clear that the account username is an email address, since people need an email to join the app.

**What was missing in the original prompt:** The sign-up design (Problem 2, follow-up 9) didn't say accounts should be keyed on
email; the form asked for a username.

### Follow-up 2

There won't be a pilot user quote in time: replace the yellow TODO placeholders so the report and slides are complete.
Also asked whether this is a Tier 3 project.

**What was missing in the original prompt:** The plan assumed a pilot user's results would fill the Impact section; it needed an
honest version without one.

### Follow-up 3

Safety review: confirm there's an audit log for all agents like in earlier homework; check the last homework (HW6) and make
sure the agents are secure against prompt injection; and make sure people can't use the chat as a general AI chatbot, so the
agents only talk about books.

**What was missing in the original prompt:** The safety design hadn't covered injection hidden in third-party catalog text,
an HW6-style tripwire, logging of non-agent safety events, or off-topic use of the AI.

### Follow-up 4

Fix: after joining a reader room, the home page still showed "Join them". Add a third card on the home page, next to the
people and Booksy cards, listing the rooms the reader has joined so they're one click away.

**What was missing in the original prompt:** The home page design didn't account for readers returning to rooms they had
already joined.

### Follow-up 5

Asked whether graders can open the website, report, and slides by double-clicking (report and slides yes; the app runs
from the README). Then, per the instructor's note that only the report and slides HTML (plus an optional video) are
submitted: put the GitHub repo URL in both files, organize the folder like previous assignments, make sure no API keys or
private data are included, and push to a public GitHub repo.

**What was missing in the original prompt:** The submission format changed after the original instructions: the repo link
now has to live inside the report and slides, since Canvas takes only files.
