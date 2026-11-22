import axe from 'axe-core'

/** Return the accessibility violations axe-core finds in `container`. */
export async function findA11yViolations(
  container: Element,
): Promise<axe.Result[]> {
  const results = await axe.run(container)
  return results.violations
}
