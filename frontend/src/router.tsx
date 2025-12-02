import React from "react";

interface RouterContextValue {
  path: string;
  navigate: (to: string) => void;
}

const RouterContext = React.createContext<RouterContextValue | undefined>(
  undefined
);

export const RouterProvider: React.FC<{ children: React.ReactNode }> = ({
  children
}) => {
  const [path, setPath] = React.useState(
    window.location.pathname + window.location.search
  );

  React.useEffect(() => {
    const handler = () => {
      setPath(window.location.pathname + window.location.search);
    };
    window.addEventListener("popstate", handler);
    return () => window.removeEventListener("popstate", handler);
  }, []);

  const navigate = (to: string) => {
    if (to === path) return;
    window.history.pushState({}, "", to);
    setPath(to);
  };

  return (
    <RouterContext.Provider value={{ path, navigate }}>
      {children}
    </RouterContext.Provider>
  );
};

export function useRouter(): RouterContextValue {
  const ctx = React.useContext(RouterContext);
  if (!ctx) {
    throw new Error("useRouter must be used within RouterProvider");
  }
  return ctx;
}

export const Link: React.FC<{
  to: string;
  className?: string;
  children: React.ReactNode;
}> = ({ to, className, children }) => {
  const { navigate } = useRouter();
  const onClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) {
      return; // 允许在新标签页等场景下正常跳转
    }
    e.preventDefault();
    navigate(to);
  };
  return (
    <a href={to} className={className} onClick={onClick}>
      {children}
    </a>
  );
};

