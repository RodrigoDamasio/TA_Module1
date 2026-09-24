import Shortener from "@/components/Shortener";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 px-4 py-16">
      <div className="max-w-xl text-center">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">URL Shortener</h1>
        <p className="mt-3 text-zinc-600 dark:text-zinc-400">
          Paste a long link and get a short one you can share.
        </p>
      </div>
      <Shortener />
    </main>
  );
}
