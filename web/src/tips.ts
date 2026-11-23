import type { PostponeReason } from '@task-master/api-client'

export interface TipSection {
  heading: string
  paragraphs: string[]
  /** Before and after: a vague version, then the version that gets done. */
  examples?: { before: string; after: string }[]
}

export interface TipArticle {
  id: PostponeReason
  title: string
  summary: string
  sections: TipSection[]
}

/** The guide behind each postpone reason, shown on the Tips page. */
export const TIP_ARTICLES: TipArticle[] = [
  {
    id: 'stuck',
    title: "When you don't know where to start",
    summary: 'A task you cannot picture starting is a task you will put off. Make the first step small and physical.',
    sections: [
      {
        heading: 'Why it happens',
        paragraphs: [
          'Vague tasks ask you to decide before you can act: what first, how much, in what order. Your brain treats that uncertainty as effort, so it reaches for something easier.',
          'The task is rarely too hard. It is too foggy to begin.',
        ],
      },
      {
        heading: 'The fix: shrink the first step',
        paragraphs: [
          'Rewrite the next step as one physical action you could start in the next two minutes without deciding anything. Aim for 15 minutes or less.',
          'A quick test: if the step contains a verb like "handle", "sort out" or "work on", it is still a project, not a step.',
        ],
        examples: [
          { before: 'Do taxes', after: 'Download Form 16 from the employer portal' },
          { before: 'Plan the Goa trip', after: 'Open the calendar and pick three possible weekends' },
          { before: 'Write the proposal', after: 'Write five bullet points of what the client asked for' },
        ],
      },
      {
        heading: 'If it is still too big',
        paragraphs: [
          'Split it into smaller tasks, each with its own first step. A task that needs more than a handful of steps is usually two or three tasks in disguise.',
        ],
      },
    ],
  },
  {
    id: 'dreading',
    title: "When you don't want to do it",
    summary: 'You are avoiding a feeling, not the task. Lower the bar until starting feels easy.',
    sections: [
      {
        heading: 'Why it happens',
        paragraphs: [
          'Boring, stressful or awkward tasks come with a small unpleasant feeling. Postponing makes it go away for now, so it feels like relief, and the dread grows a little each time.',
          'The feeling is strongest before you start. Once you are moving, it usually fades.',
        ],
      },
      {
        heading: 'The fix: make starting tiny',
        paragraphs: [
          'Commit to five minutes only. When the time is up you may stop with a clear conscience; most of the time you will keep going.',
          'Pair it with something you enjoy, such as a favourite playlist or a coffee, and put it first in tomorrow’s Top 3 so it is done before the day fills up.',
        ],
        examples: [
          { before: 'Call the bank about the fee', after: 'Set a 5-minute timer, find the number, dial' },
          { before: 'Clean the garage', after: 'Fill one box with things to give away' },
          { before: 'Reply to the difficult email', after: 'Write a two-line first draft, without sending it' },
        ],
      },
    ],
  },
  {
    id: 'blocked',
    title: "When something's in the way",
    summary: 'A blocker you can name is a blocker you can clear. Make it explicit, then make it a step.',
    sections: [
      {
        heading: 'Name the blocker precisely',
        paragraphs: [
          'Write down exactly what you are waiting on and who can unblock it. "Waiting on Sam" is a start; "Sam’s pricing sheet, needed to finish section 3" is something you can act on.',
          'Then turn it into a step of its own: a message, a reminder, or a question to ask.',
        ],
        examples: [
          { before: 'Waiting on Sam', after: 'Email Sam asking for the pricing sheet by Thursday' },
          { before: 'Need the landlord’s approval', after: 'Text the landlord the two paint colours to choose from' },
        ],
      },
      {
        heading: 'When the blocker is time',
        paragraphs: [
          'If there is genuinely no time, lower the task’s time limit so it fits your next free slot, even if that only covers part of it.',
          'Be honest with yourself, though. When a task is postponed for "no time" again and again, the real reason is often dread. Task Master asks about it on the third time.',
        ],
      },
    ],
  },
  {
    id: 'other',
    title: 'Planning around everything else',
    summary: 'Sometimes life simply gets in the way. Pick a realistic date and protect time for it.',
    sections: [
      {
        heading: 'Replan, do not just move',
        paragraphs: [
          'Illness, travel and urgent work are real reasons. The risk is pushing a task to tomorrow out of habit and then pushing it again.',
          'Look at the week ahead and choose a day that actually has room. Protect a slot for it, and keep the note you wrote so you remember why it moved.',
        ],
        examples: [
          { before: 'Move it to tomorrow', after: 'Move it to Saturday morning, when the week is quieter' },
        ],
      },
    ],
  },
]

export function tipArticle(id: PostponeReason): TipArticle | undefined {
  return TIP_ARTICLES.find((article) => article.id === id)
}
