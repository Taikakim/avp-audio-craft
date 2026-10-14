// Owner: WINTERMUTE (created 2026-10-13)
// Whether the prompt pane shows the NOTES box instead of the prompt / negative prompt. View state
// only: the notes themselves are RenderSettings.notes, per target, saved with the session.
class PromptNotesView {
  open = $state(false);
  /** The comment (`notes`) of the preset last recalled into the prompt pane, and its name. */
  comment = $state("");
  commentFrom = $state("");
  toggle(): void {
    this.open = !this.open;
  }
  showComment(from: string, text: string): void {
    this.commentFrom = text ? from : "";
    this.comment = text;
  }
}

export const promptNotes = new PromptNotesView();
