// Minimal worker pool: run `total` indexed tasks, at most `limit` at a time.
// `worker` is invoked per index and is expected to handle its own results/errors
// (so the UI can fill cards in as each verdict returns).

export async function runPool(
  total: number,
  limit: number,
  worker: (index: number) => Promise<void>,
): Promise<void> {
  let next = 0;
  const runners: Promise<void>[] = [];
  const take = async (): Promise<void> => {
    while (next < total) {
      const i = next++;
      await worker(i);
    }
  };
  for (let i = 0; i < Math.min(limit, total); i++) {
    runners.push(take());
  }
  await Promise.all(runners);
}
