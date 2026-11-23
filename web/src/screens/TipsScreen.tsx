import type { PostponeReason } from '@task-master/api-client'
import { useEffect, useRef, useState } from 'react'

import { TIP_ARTICLES, tipArticle } from '@/tips'

/** Guides for the moments you put things off, one per postpone reason. */
export function TipsScreen({ initialTip }: { initialTip?: PostponeReason | undefined }) {
  const [selected, setSelected] = useState<PostponeReason>(initialTip ?? 'stuck')
  const article = tipArticle(selected) ?? TIP_ARTICLES[0]
  const headingRef = useRef<HTMLHeadingElement>(null)

  // Opened from a tip pop-up: move focus to that guide.
  useEffect(() => {
    if (initialTip) headingRef.current?.focus()
  }, [initialTip])

  function handleSelect(id: PostponeReason) {
    setSelected(id)
    requestAnimationFrame(() => headingRef.current?.focus())
  }

  if (!article) return null
  return (
    <section className="stack-lg" aria-labelledby="tips-heading">
      <div>
        <h1 id="tips-heading" className="page-title">
          Tips
        </h1>
        <p className="muted lede">
          Short guides for the moments you put something off, with examples of what to do instead.
        </p>
      </div>

      <nav aria-label="Guides" className="guide-list">
        {TIP_ARTICLES.map((item) => (
          <button
            key={item.id}
            type="button"
            className="guide-card"
            aria-current={item.id === selected ? 'true' : undefined}
            onClick={() => handleSelect(item.id)}
          >
            <span className="guide-title">{item.title}</span>
            <span className="guide-summary">{item.summary}</span>
          </button>
        ))}
      </nav>

      <article className="guide" aria-labelledby="guide-title">
        <h2 id="guide-title" ref={headingRef} tabIndex={-1}>
          {article.title}
        </h2>
        <p className="guide-lede">{article.summary}</p>
        {article.sections.map((section) => (
          <section key={section.heading} className="guide-section">
            <h3>{section.heading}</h3>
            {section.paragraphs.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
            {section.examples && (
              <table className="examples">
                <caption className="visually-hidden">Examples for {section.heading}</caption>
                <thead>
                  <tr>
                    <th scope="col">Instead of</th>
                    <th scope="col">Try</th>
                  </tr>
                </thead>
                <tbody>
                  {section.examples.map((example) => (
                    <tr key={example.before}>
                      <td>{example.before}</td>
                      <td>{example.after}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        ))}
      </article>
    </section>
  )
}
