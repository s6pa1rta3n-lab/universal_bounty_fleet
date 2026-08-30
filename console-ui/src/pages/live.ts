export function liveTemplate(): string {
  return `
    <section class="hero">
      <p class="kicker">Fortified Enterprise Fleet</p>
      <h1 id="banner" class="status PENDING">PENDING</h1>
      <p id="banner-sub" class="lede">Waiting for fleet state.</p>
    </section>
    <main class="cards">
      <section class="card">
        <h2>Bounty</h2>
        <div id="bounty" class="empty">No live bounty yet.</div>
      </section>
      <section class="card">
        <h2>Trace</h2>
        <div id="timeline" class="empty">Intake, Executor, and Auditor write here.</div>
      </section>
      <section class="card">
        <h2>Registry</h2>
        <div id="registry"></div>
      </section>
    </main>`;
}
