// Drives the live Bookend app in real Chrome through one full run (every agent) and captures the
// screenshots used in report.html. Needs the app running on :8000 (python app.py --no-browser).
// Run from the repo folder:   node frontend/scripts/app_check.mjs
// RESETS the sample data first. Writes JPEGs to output/screenshots/ and what each step returned to
// output/screenshots/results.json.
import puppeteer from 'puppeteer-core'
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../output/screenshots')
const BASE = process.env.BOOKEND_URL || 'http://localhost:8000'
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
mkdirSync(OUT, { recursive: true })

const results = { ran_at: new Date().toISOString(), steps: [] }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

await fetch(`${BASE}/api/reset`, { method: 'POST' })

const browser = await puppeteer.launch({ executablePath: CHROME, headless: true })
const alex = await browser.newPage()
await alex.setViewport({ width: 1360, height: 860, deviceScaleFactor: 2 })

async function shot(page, name, note) {
  await sleep(600)
  await page.screenshot({ path: path.join(OUT, `${name}.jpg`), type: 'jpeg', quality: 82 })
  results.steps.push({ name, note })
  console.log('  saved', name)
}

// Sign in through the welcome screen as one of the demo readers (each tab keeps its own demo session).
async function signInAsDemo(page, name) {
  await page.goto(BASE, { waitUntil: 'networkidle0' })
  await page.evaluate(() => { localStorage.clear(); sessionStorage.clear() })
  await page.goto(BASE, { waitUntil: 'networkidle0' })
  await page.waitForSelector('.demo-reader')
  await clickText(page, '.demo-reader', name)
  await page.waitForSelector('.signed-in')
}

const clickText = (page, selector, text) =>
  page.evaluate(
    (s, t) => {
      const el = [...document.querySelectorAll(s)].find((e) => e.innerText.includes(t))
      if (!el) throw new Error(`no ${s} with "${t}"`)
      el.click()
    },
    selector,
    text,
  )

async function type(page, selector, text) {
  await page.click(selector, { clickCount: 3 })
  await page.type(selector, text)
}

const countSel = (page, sel) => page.$$eval(sel, (els) => els.length)

async function waitMore(page, sel, before, timeout = 60000) {
  await page.waitForFunction((s, n) => document.querySelectorAll(s).length > n, { timeout }, sel, before)
}

async function send(page, text, waitSel) {
  const before = waitSel ? await countSel(page, waitSel) : 0
  await type(page, '.composer input', text)
  await page.click('.composer button')
  await page.waitForFunction(() => !document.querySelector('.bubble.pending'), { timeout: 60000 })
  if (waitSel) await waitMore(page, waitSel, before)
  await sleep(500)
}

async function finishBook(page, query, firstTitle) {
  await clickText(page, '.tab', 'Home')
  await page.waitForSelector('.log')
  if (!(await page.$('.search input'))) await page.click('.log-btn')
  await page.waitForSelector('.search input')
  await type(page, '.search input', query)
  await page.click('.search button')
  await page.waitForSelector('.result', { timeout: 30000 })
  await clickText(page, '.result', firstTitle)
  await page.waitForSelector('.finish-form')
  const stars = await page.$$('.finish .stars.editable button')
  await stars[4].click()
}

// 1. Landing page
await alex.goto(BASE, { waitUntil: 'networkidle0' })
await alex.evaluate(() => { localStorage.clear(); sessionStorage.clear() })
await alex.goto(BASE, { waitUntil: 'networkidle0' })
await alex.waitForSelector('.demo-reader')
await shot(alex, '00_welcome', 'The welcome screen: create an account or log in, or try a demo reader with one click.')
await signInAsDemo(alex, 'Alex')
await alex.waitForFunction(() => document.querySelectorAll('.next-card:not(.loading)').length > 0, { timeout: 90000 })
await shot(alex, '01_home', 'The Bookend home page: the logo shelf, Log a book, Chat w/ people, Chat w/ us, and the scrolling cover rail.')
await alex.evaluate(() => document.querySelector('.next-book').scrollIntoView({ block: 'start' }))
await shot(alex, '01b_next_book', 'Your next book: the Recommendation agent ran in the background on the last book logged; below it, the shelf.')

// 2. Log a finished book
await finishBook(alex, 'project hail mary', 'Project Hail Mary')
await alex.evaluate(() => document.querySelector('.finish').scrollIntoView({ block: 'center' }))
await shot(alex, '02_finish_form', 'Alex marks Project Hail Mary finished today, 5 stars, and asks for readers from the last 30 days.')

// 3. Match (plain query, no agent)
await clickText(alex, '.finish .btn', 'Mark finished')
await alex.waitForSelector('.match', { timeout: 60000 })
await alex.evaluate(() => document.querySelector('.match').scrollIntoView({ block: 'center' }))
results.match_hail_mary = await alex.$eval('.match', (e) => e.innerText)
await shot(alex, '03_match', 'Code finds 3 readers who finished it in the last 30 days (no agent needed).')

// 4. Join with the Host on
await clickText(alex, '.choice .btn', 'Join the readers')
await alex.waitForSelector('.chat')
await waitMore(alex, '.bubble.ai.host:not(.typing)', 1)
results.host_welcome = await alex.$$eval('.bubble.ai.host:not(.typing)', (b) => b.at(-1).innerText)
await shot(alex, '04_host_welcome', 'Alex joins the room with the Discussion Host on; the Host welcomes Alex with a question.')

// 5. Moderation
await send(alex, "The reveal that he didn't volunteer got me. I spent the whole book thinking he was a hero.", '.row.mine')
await send(alex, "Jordan you're an idiot if you think Rocky is the best part", '.hidden-msg')
await send(alex, 'anyone want to keep talking? add me on insta at alex.reads', '.hidden-msg')
await shot(alex, '05_moderation', 'One message posts; an insult is hidden by the Moderator agent; an Instagram handle is hidden by the code screen. Only Alex sees them.')

// 6. Priya's view: hidden messages are invisible to her; she calls the Host
const priya = await browser.newPage()
await priya.setViewport({ width: 1360, height: 860, deviceScaleFactor: 2 })
await signInAsDemo(priya, 'Priya')
await clickText(priya, '.tab', 'chat about it')
await priya.waitForSelector('.chat')
await clickText(priya, '.room-item', 'Project Hail Mary')
await priya.waitForSelector('.composer input')
results.priya_sees_hidden = await countSel(priya, '.hidden-msg')
const hostBefore = await countSel(priya, '.bubble.ai.host:not(.typing)')
await send(priya, '@host was he actually a coward, or is the book more forgiving than that?')
await waitMore(priya, '.bubble.ai.host:not(.typing)', hostBefore, 90000)
results.host_reply = await priya.$$eval('.bubble.ai.host:not(.typing)', (b) => b.at(-1).innerText)
await shot(priya, '06_priya_host_reply', "Priya's view: Alex's hidden messages aren't there. Priya mentions @host and the Host answers.")
await priya.close()

// 7. Matchmaker: a book nobody finished recently
await finishBook(alex, 'the remains of the day ishiguro', 'The Remains of the Day')
await clickText(alex, '.finish .btn', 'Mark finished')
await alex.waitForSelector('.match', { timeout: 90000 })
await alex.evaluate(() => document.querySelector('.match').scrollIntoView({ block: 'center' }))
results.matchmaker = await alex.$eval('.match', (e) => e.innerText)
await shot(alex, '07_matchmaker', 'Nobody finished The Remains of the Day recently, so the Matchmaker agent finds a related book with readers.')

// 8. Book Companion
await clickText(alex, '.choice .btn', 'Talk with Booksy')
await alex.waitForSelector('.chat .composer input')
await send(alex, 'I just finished it. Was Stevens wrong to stay loyal to Lord Darlington?', '.bubble.ai.companion:not(.typing)')
await send(alex, 'What did Miss Kenton say in her very last letter, word for word?', '.bubble.ai.companion:not(.typing)')
results.companion = await alex.$$eval('.bubble.ai.companion:not(.typing)', (b) => b.slice(-2).map((x) => x.innerText))
await shot(alex, '08_companion', 'The Book Companion answers, labels its basis, and says when it is not sure instead of inventing a quote.')

await shot(alex, '08b_chats_people_vs_ai', 'The Chats tab: rooms with real people (blue) and with AI (coral) are separate, with a banner saying which one you are in, and the globe.')

// 9. Recommendations
await clickText(alex, '.tab', 'Your Next Book')
await alex.waitForSelector('.chat .composer input')
await send(alex, 'I loved Project Hail Mary and Circe. Something with a big heart and an unusual friendship?', '.pick')
results.recs = await alex.$$eval('.pick', (p) => p.map((x) => x.innerText.split('\n')[0]))
await alex.evaluate(() => document.querySelector('.messages').scrollTo(0, 99999))
await shot(alex, '09_recommendations', 'The Recommendation agent suggests real catalog books; one has readers discussing it now.')

// 10. Behind the scenes
await clickText(alex, '.tab', 'Behind the scenes')
await alex.waitForSelector('.diagram')
await sleep(1500)
await shot(alex, '10_agent_team', 'The agent hand-off diagram and measured tokens and cost per agent.')
await alex.evaluate(() => document.querySelector('.behind-cols').scrollIntoView())
await clickText(alex, '.run-head', 'Recommendation')
await sleep(500)
await shot(alex, '11_run_trace', "One Recommendation run expanded: each tool call, its arguments and result, and the agent's answer. Right: the moderation log.")

await browser.close()
writeFileSync(path.join(OUT, 'results.json'), JSON.stringify(results, null, 2))
console.log('done:', results.steps.length, 'screenshots')
