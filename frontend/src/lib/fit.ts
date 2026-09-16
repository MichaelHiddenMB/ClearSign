/**
 * Shrinks any line whose longest word is wider than the container so the word
 * fits on one line, instead of letting the browser break it mid-word.
 * Lines that already fit keep the full reading size.
 */
export function fitLines(container: HTMLElement, baseSize: number, selector = '.surface__line'): void {
  const lines = container.querySelectorAll<HTMLElement>(selector)
  const available = container.clientWidth - horizontalPadding(container)
  if (available <= 0) return

  for (const line of lines) {
    line.style.fontSize = ''
    // Measure on a single unbroken line; a word the browser has already split
    // across lines would otherwise report the width of the container.
    line.style.whiteSpace = 'nowrap'
    const widest = longestWordWidth(line)
    line.style.whiteSpace = ''
    if (widest > available) {
      line.style.fontSize = `${Math.max(16, Math.floor(baseSize * (available / widest)))}px`
    }
  }
}

function horizontalPadding(el: HTMLElement): number {
  const cs = getComputedStyle(el)
  return parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight)
}

function longestWordWidth(el: HTMLElement): number {
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
  const range = document.createRange()
  let widest = 0
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node.textContent ?? ''
    const re = /\S+/g
    let match: RegExpExecArray | null
    while ((match = re.exec(text))) {
      range.setStart(node, match.index)
      range.setEnd(node, match.index + match[0].length)
      widest = Math.max(widest, range.getBoundingClientRect().width)
    }
  }
  return widest
}
