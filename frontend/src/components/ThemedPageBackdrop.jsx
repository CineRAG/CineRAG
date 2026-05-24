import bannerPosterWall from "../assets/banner2.png";
import bannerCinema from "../assets/banner7.png";
import bannerFlyers from "../assets/banner8.png";
import bannerVhs from "../assets/banner.png";
import { CinemaNeonBackdrop } from "./CinemaNeonBackdrop.jsx";
import { useTheme } from "../context/ThemeContext.jsx";

const CHAT_BACKGROUNDS = {
  light: bannerVhs,
};

const PROFILE_LAYERS = {
  light: {
    primary: bannerFlyers,
    strip: bannerVhs,
  },
  dark: {
    primary: bannerPosterWall,
    secondary: bannerCinema,
    strip: bannerVhs,
  },
};

function ProfileBackdrop({ theme }) {
  const layers = PROFILE_LAYERS[theme];
  if (!layers) return null;

  return (
    <div className="themed-page-backdrop themed-page-backdrop--profile" aria-hidden>
      <div
        className="themed-page-backdrop__layer themed-page-backdrop__layer--profile-base"
        style={{ backgroundImage: `url(${layers.primary})` }}
      />
      {layers.secondary ? (
        <div
          className="themed-page-backdrop__layer themed-page-backdrop__layer--profile-accent"
          style={{ backgroundImage: `url(${layers.secondary})` }}
        />
      ) : null}
      {layers.strip ? (
        <div
          className="themed-page-backdrop__layer themed-page-backdrop__layer--profile-strip"
          style={{ backgroundImage: `url(${layers.strip})` }}
        />
      ) : null}
      <div className="themed-page-backdrop__vignette themed-page-backdrop__vignette--profile" />
    </div>
  );
}

function ChatBackdrop({ theme }) {
  if (theme === "dark") {
    return <CinemaNeonBackdrop variant="dark" />;
  }

  const image = CHAT_BACKGROUNDS[theme];
  if (!image) return null;

  return (
    <div className="themed-page-backdrop themed-page-backdrop--chat" aria-hidden>
      <div
        className={`themed-page-backdrop__image themed-page-backdrop__image--${theme} themed-page-backdrop__image--chat`}
        style={{ backgroundImage: `url(${image})` }}
      />
      <div className="themed-page-backdrop__wash" />
    </div>
  );
}

export function ThemedPageBackdrop({ page = "chat" }) {
  const { theme, isNeon } = useTheme();

  if (isNeon) return null;

  if (page === "profile") {
    return <ProfileBackdrop theme={theme} />;
  }

  return <ChatBackdrop theme={theme} />;
}
