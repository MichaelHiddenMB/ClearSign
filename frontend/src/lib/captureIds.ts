/** Element ids that tie each capture's tab to its panel for assistive technology. */
export function tabId(id: number) {
  return `capture-tab-${id}`
}

export function panelId(id: number) {
  return `capture-panel-${id}`
}
