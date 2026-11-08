import Link from "next/link";
import { redirect } from "next/navigation";
import { authEnabled, getUser } from "@/lib/auth0";

export default async function Landing() {
  const user = await getUser();
  if (user && authEnabled) redirect("/today");

  return (
    <div className="min-h-dvh flex flex-col justify-between py-10 max-w-md mx-auto">
      <div>
        <div className="w-14 h-14 rounded-2xl bg-brand text-white grid place-items-center text-2xl font-bold">A</div>
        <h1 className="text-4xl font-bold tracking-tight mt-8 leading-tight">What you eat is not what you absorb.</h1>
        <p className="text-ink-2 mt-4 text-lg">
          A cup of tea with a lentil curry can cut the iron you absorb by more than three quarters. Absorb shows you that hidden
          effect, and the smallest change that fixes it.
        </p>
      </div>

      <div className="space-y-3 mt-10">
        {authEnabled ? (
          <>
            <a href="/auth/login?returnTo=/today" className="btn btn-primary w-full">Sign in</a>
            <a href="/auth/login?screen_hint=signup&returnTo=/profile?onboarding=1" className="btn btn-ghost w-full">Create an account</a>
          </>
        ) : (
          <Link href="/today" className="btn btn-primary w-full">Open the demo</Link>
        )}
        <div className="flex justify-center gap-6 text-sm pt-2">
          <Link href="/interactions" className="text-brand font-medium">Explore the interaction map</Link>
          <Link href="/validation" className="text-brand font-medium">How accurate is it?</Link>
        </div>
        <p className="text-xs text-muted text-center pt-4">
          Not medical advice. Estimates come from published population-level studies. Absorb does not diagnose or treat iron deficiency.
        </p>
      </div>
    </div>
  );
}
