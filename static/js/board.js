/* Progressive enhancement for the board — plan 001 §7.
 *
 * The one hand-written script in the project. No build step: this is the file
 * the browser runs. Everything it does is an enhancement, so a browser that
 * never runs it is left with a board that works — every summary open, the
 * steps scrollable.
 *
 * On a phone it does two things: collapses each summary to its title and
 * company until it is tapped, and turns the steps into one card at a time with
 * an arrow either side, so nothing has to be swiped sideways. On a laptop it
 * drives the same arrows a card at a time, standing in for the scrollbar the
 * stylesheet hides.
 */
(() => {
  "use strict";

  // Matches the breakpoint in assets/board.css. The stylesheet decides what the
  // phone looks like; this only decides when the behaviour changes with it.
  const PHONE = window.matchMedia("(max-width: 30rem)");
  const STILL = window.matchMedia("(prefers-reduced-motion: reduce)");

  const root = document.documentElement;

  function setExpanded(card, expanded) {
    card.toggleAttribute("data-collapsed", !expanded);
    card
      .querySelector("[data-summary-toggle]")
      .setAttribute("aria-expanded", String(expanded));
  }

  function cards(steps) {
    return Array.from(steps.querySelector("[data-steps-track]").children);
  }

  function track(steps) {
    return steps.querySelector("[data-steps-track]");
  }

  function offsets(steps) {
    const all = cards(steps);
    return all.map((card) => card.offsetLeft - all[0].offsetLeft);
  }

  function scrollTrack(steps, left) {
    track(steps).scrollTo({ left, behavior: STILL.matches ? "auto" : "smooth" });
  }

  /* Where the track stands, and whether an arrow could move it.
   *
   * A phone keeps an index, because the card is the track and the reader taps
   * through a known list. A laptop reads the scroll position instead, because
   * the wheel and the trackpad still move the track and an index would go
   * stale the moment they did. */
  function position(steps) {
    const all = cards(steps);
    const element = track(steps);

    if (PHONE.matches) {
      const at = Number(element.dataset.stepsIndex || 0);
      return { start: at <= 0, end: at >= all.length - 1, movable: all.length > 1 };
    }

    const furthest = element.scrollWidth - element.clientWidth;
    return {
      start: element.scrollLeft <= 1,
      end: element.scrollLeft >= furthest - 1,
      movable: furthest > 1,
    };
  }

  function syncArrows(steps) {
    const { start, end, movable } = position(steps);
    const prev = steps.querySelector("[data-steps-prev]");
    const next = steps.querySelector("[data-steps-next]");

    if (PHONE.matches) {
      // A phone card is the width of the track, so hiding an arrow would
      // resize the card under the reader's thumb. The ends grey out instead.
      prev.hidden = next.hidden = !movable;
      prev.disabled = start;
      next.disabled = end;
      return;
    }

    // A laptop card is a fixed width, so an arrow can leave without moving
    // anything: it shows only while it has somewhere to go.
    prev.hidden = !movable || start;
    next.hidden = !movable || end;
    prev.disabled = next.disabled = false;
  }

  function showStep(steps, index) {
    const all = cards(steps);
    const wanted = Math.max(0, Math.min(all.length - 1, index));

    if (all.length > 0) {
      scrollTrack(steps, offsets(steps)[wanted]);
    }
    track(steps).dataset.stepsIndex = String(wanted);
    syncArrows(steps);
  }

  function move(steps, direction) {
    if (PHONE.matches) {
      showStep(steps, Number(track(steps).dataset.stepsIndex || 0) + direction);
      return;
    }

    // The next card edge past where the track stands, in the direction asked
    // for — so a click lands on a boundary however the track got here.
    const at = track(steps).scrollLeft;
    const edges = offsets(steps);
    const target =
      direction > 0
        ? edges.find((edge) => edge > at + 1)
        : edges.filter((edge) => edge < at - 1).pop();

    scrollTrack(steps, target === undefined ? at : target);
  }

  function apply() {
    document
      .querySelectorAll("[data-summary]")
      .forEach((card) => setExpanded(card, !PHONE.matches));
    document.querySelectorAll("[data-steps]").forEach((steps) => showStep(steps, 0));
  }

  function onScroll(event) {
    const element = event.target;
    if (element instanceof Element && element.matches("[data-steps-track]")) {
      syncArrows(element.closest("[data-steps]"));
    }
  }

  function onClick(event) {
    const toggle = event.target.closest("[data-summary-toggle]");
    if (toggle) {
      const card = toggle.closest("[data-summary]");
      setExpanded(card, card.hasAttribute("data-collapsed"));
      return;
    }

    const arrow = event.target.closest("[data-steps-prev], [data-steps-next]");
    if (arrow) {
      move(arrow.closest("[data-steps]"), arrow.hasAttribute("data-steps-prev") ? -1 : 1);
    }
  }

  root.classList.add("has-js");
  // Delegated, so rows swapped in later are wired without re-running any of this.
  document.addEventListener("click", onClick);
  // `scroll` does not bubble, so this listens on the way down instead.
  document.addEventListener("scroll", onScroll, true);
  PHONE.addEventListener("change", apply);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply);
  } else {
    apply();
  }
})();
