import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, type Account, type MemberSummary } from "./api";
import { ACCOUNT_FALLBACK } from "../data/fallback";

interface ProfileCtx {
  account: Account;
  activeId: string;
  active: MemberSummary;
  isGuardian: boolean;
  setActiveId: (id: string) => void;
}
const Ctx = createContext<ProfileCtx | null>(null);

export function ProfileProvider({ children }: { children: ReactNode }) {
  const [account, setAccount] = useState<Account>(ACCOUNT_FALLBACK);
  const [activeId, setActiveId] = useState<string>(ACCOUNT_FALLBACK.guardian_id);
  useEffect(() => { api.account().then((a) => { if (a) setAccount(a); }); }, []);

  const value = useMemo<ProfileCtx>(() => {
    const active = account.members.find((m) => m.member_id === activeId) ?? account.members[0];
    return { account, activeId, active, isGuardian: account.guardian_id === activeId, setActiveId };
  }, [account, activeId]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useProfile() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useProfile must be used within ProfileProvider");
  return c;
}
