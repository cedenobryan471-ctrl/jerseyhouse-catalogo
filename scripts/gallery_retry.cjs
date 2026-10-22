// Three retries after the initial attempt; fresh runs resume committed progress.
function recoveryAction(run) {
  if (run.head_branch !== 'main' || run.event !== 'workflow_dispatch' || run.conclusion !== 'failure') return 'none';
  const automatic = run.display_title === 'Galerías automáticas' || run.run_number >= 81 && run.display_title === 'Recuperar galerías sin IA';
  if (!automatic) return 'none';
  return (run.run_attempt || 1) <= 3 ? 'retry' : 'next';
}
module.exports = { recoveryAction };
