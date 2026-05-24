import bannerVhs from "../assets/banner.png";
import bannerPosters from "../assets/banner2.png";
import bannerFilm3 from "../assets/banner3.png";
import bannerFilm4 from "../assets/banner4.png";

export function CinemaNeonBackdrop({ variant = "neon" }) {
  return (
    <div className={`cinema-neon-backdrop cinema-neon-backdrop--${variant}`} aria-hidden>
      <div
        className="cinema-neon-backdrop__film cinema-neon-backdrop__film--base"
        style={{ backgroundImage: `url(${bannerPosters})` }}
      />
      <div
        className="cinema-neon-backdrop__film cinema-neon-backdrop__film--accent"
        style={{ backgroundImage: `url(${bannerFilm3})` }}
      />
      <div
        className="cinema-neon-backdrop__film cinema-neon-backdrop__film--accent-alt"
        style={{ backgroundImage: `url(${bannerFilm4})` }}
      />
      <div
        className="cinema-neon-backdrop__film cinema-neon-backdrop__film--strip"
        style={{ backgroundImage: `url(${bannerVhs})` }}
      />
      {variant === "neon" ? (
        <>
          <div className="cinema-neon-backdrop__glow cinema-neon-backdrop__glow--top" />
          <div className="cinema-neon-backdrop__glow cinema-neon-backdrop__glow--center" />
        </>
      ) : null}
      <div className="cinema-neon-backdrop__vignette" />
    </div>
  );
}
