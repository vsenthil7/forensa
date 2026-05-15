/**
 * caption-overlay.ts - reusable BDD-style captions for Forensa demo videos.
 *
 * Ported from C:\Users\v_sen\Documents\Projects\0001_Hack0014_Vertex_Swarm_Tashi\auditex\frontend\tests\demo\caption-overlay.ts
 * (sibling hackathon project). The overlay system is app-agnostic so we
 * use it verbatim aside from the EU AI Act badge text on the title card,
 * which is replaced with EU AI ACT + GDPR for Forensa's regulator
 * narrative.
 *
 * Each scene shows: scene number, title, Given/When/Then, optional Test
 * Data, and optional Expected Outcome, before the actual UI action plays
 * out. No audio needed.
 */
import type { Page } from '@playwright/test'

export interface CaptionScene {
  scene: string
  title: string
  given: string
  when: string
  then: string
  testData?: string[]
  expected?: string
  holdMs?: number
}

export const READ_SHORT = 2500
export const READ_LONG = 4500
export const ACTION_PAUSE = 1200

export async function showCaption(page: Page, opts: CaptionScene): Promise<void> {
  const tdHtml = opts.testData
    ? `<div class="td"><div class="td-h">Test Data</div><ul>${opts.testData.map(d => `<li>${d}</li>`).join('')}</ul></div>`
    : ''
  const expHtml = opts.expected
    ? `<div class="exp"><div class="exp-h">Expected Outcome</div><div class="exp-v">${opts.expected}</div></div>`
    : ''
  await page.evaluate((args) => {
    const existing = document.getElementById('demo-caption')
    if (existing) existing.remove()
    const div = document.createElement('div')
    div.id = 'demo-caption'
    div.innerHTML = `
      <style>
        #demo-caption {
          position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
          z-index: 2147483647;
          background: linear-gradient(135deg, #1e1b4b 0%, #3730a3 100%);
          color: #fefce8; font-family: -apple-system, Segoe UI, Roboto, sans-serif;
          display: flex; flex-direction: column; justify-content: center; align-items: center;
          padding: 70px; box-sizing: border-box;
          animation: fadeIn 0.3s ease-out;
        }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        #demo-caption .scene { font-size: 20px; color: #a5b4fc; letter-spacing: 5px; text-transform: uppercase; margin-bottom: 14px; font-weight: 600; }
        #demo-caption .title { font-size: 50px; font-weight: 800; margin-bottom: 40px; text-align: center; letter-spacing: -1px; }
        #demo-caption .gwt { display: flex; flex-direction: column; gap: 18px; max-width: 900px; width: 100%; font-size: 24px; line-height: 1.4; }
        #demo-caption .gwt .row { display: flex; gap: 20px; align-items: baseline; }
        #demo-caption .gwt .k { color: #fbbf24; font-weight: 700; min-width: 88px; }
        #demo-caption .gwt .v { color: #fefce8; }
        #demo-caption .td, #demo-caption .exp { margin-top: 28px; padding: 20px 28px; background: rgba(0,0,0,0.25); border-radius: 12px; max-width: 900px; width: 100%; }
        #demo-caption .td-h, #demo-caption .exp-h { color: #a5b4fc; font-size: 16px; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 8px; font-weight: 700; }
        #demo-caption .td ul { margin: 0; padding-left: 22px; font-size: 18px; color: #e0e7ff; line-height: 1.55; }
        #demo-caption .exp-v { font-size: 22px; color: #4ade80; font-weight: 600; }
      </style>
      <div class="scene">${args.scene}</div>
      <div class="title">${args.title}</div>
      <div class="gwt">
        <div class="row"><div class="k">GIVEN</div><div class="v">${args.given}</div></div>
        <div class="row"><div class="k">WHEN</div><div class="v">${args.when}</div></div>
        <div class="row"><div class="k">THEN</div><div class="v">${args.then}</div></div>
      </div>
      ${args.tdHtml}
      ${args.expHtml}
    `
    document.body.appendChild(div)
  }, { scene: opts.scene, title: opts.title, given: opts.given, when: opts.when, then: opts.then, tdHtml, expHtml })
  await page.waitForTimeout(opts.holdMs ?? READ_LONG)
}

export async function hideCaption(page: Page): Promise<void> {
  await page.evaluate(() => {
    const el = document.getElementById('demo-caption')
    if (el) {
      ;(el as HTMLElement).style.transition = 'opacity 0.3s'
      ;(el as HTMLElement).style.opacity = '0'
      setTimeout(() => el.remove(), 350)
    }
  })
  await page.waitForTimeout(500)
}

export async function showTitleCard(page: Page, text: string, subtext: string, holdMs = 3500): Promise<void> {
  await page.evaluate(({ text, subtext }) => {
    const existing = document.getElementById('demo-title')
    if (existing) existing.remove()
    const div = document.createElement('div')
    div.id = 'demo-title'
    div.innerHTML = `
      <style>
        #demo-title { position: fixed; inset: 0; z-index: 2147483647; background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); color: #fefce8; font-family: -apple-system, Segoe UI, Roboto, sans-serif; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 40px; }
        #demo-title .big { font-size: 88px; font-weight: 800; letter-spacing: -2px; margin-bottom: 22px; }
        #demo-title .sub { font-size: 28px; color: #a5b4fc; font-weight: 500; text-align: center; max-width: 1000px; line-height: 1.35; }
        #demo-title .badge { display: inline-block; padding: 6px 18px; background: #22c55e; color: #052e16; border-radius: 999px; font-size: 16px; font-weight: 700; letter-spacing: 2px; margin-top: 36px; }
      </style>
      <div class="big">${text}</div>
      <div class="sub">${subtext}</div>
      <div class="badge">EU AI ACT + GDPR EVIDENCE</div>
    `
    document.body.appendChild(div)
  }, { text, subtext })
  await page.waitForTimeout(holdMs)
  await page.evaluate(() => {
    const el = document.getElementById('demo-title')
    if (el) { (el as HTMLElement).style.transition = 'opacity 0.4s'; (el as HTMLElement).style.opacity = '0'; setTimeout(() => el.remove(), 450) }
  })
  await page.waitForTimeout(500)
}
