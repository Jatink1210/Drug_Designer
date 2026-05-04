/**
 * Animation Utilities - Apple Design System
 * 
 * Implements FR-UI-004: Animation System
 * 
 * Provides programmatic animation helpers for React components
 * using spring physics and natural motion curves.
 */

/**
 * Spring physics configuration
 */
export interface SpringConfig {
  stiffness?: number;
  damping?: number;
  mass?: number;
}

/**
 * Default spring configurations (Apple-style)
 */
export const springPresets = {
  // Gentle spring for subtle interactions
  gentle: {
    stiffness: 120,
    damping: 14,
    mass: 1,
  },
  // Default spring for most interactions
  default: {
    stiffness: 170,
    damping: 26,
    mass: 1,
  },
  // Wobbly spring for playful interactions
  wobbly: {
    stiffness: 180,
    damping: 12,
    mass: 1,
  },
  // Stiff spring for quick, snappy interactions
  stiff: {
    stiffness: 210,
    damping: 20,
    mass: 1,
  },
  // Slow spring for dramatic effects
  slow: {
    stiffness: 280,
    damping: 60,
    mass: 1,
  },
};

/**
 * Easing functions (Apple-style cubic bezier curves)
 */
export const easings = {
  spring: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
  smooth: 'cubic-bezier(0.4, 0, 0.2, 1)',
  easeIn: 'cubic-bezier(0.4, 0, 1, 1)',
  easeOut: 'cubic-bezier(0, 0, 0.2, 1)',
  easeInOut: 'cubic-bezier(0.4, 0, 0.2, 1)',
};

/**
 * Duration presets (in milliseconds)
 */
export const durations = {
  instant: 100,
  fast: 200,
  normal: 300,
  slow: 400,
  slower: 600,
};

/**
 * Check if user prefers reduced motion
 */
export const prefersReducedMotion = (): boolean => {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
};

/**
 * Get animation duration based on user preference
 * Returns 0 if user prefers reduced motion
 */
export const getAnimationDuration = (duration: number): number => {
  return prefersReducedMotion() ? 0 : duration;
};

/**
 * Stagger delay calculator for list animations
 */
export const getStaggerDelay = (index: number, baseDelay: number = 50): number => {
  return prefersReducedMotion() ? 0 : index * baseDelay;
};

/**
 * Animate element with spring physics
 * Returns a promise that resolves when animation completes
 */
export const animateSpring = (
  element: HTMLElement,
  properties: Partial<CSSStyleDeclaration>,
  config: SpringConfig = springPresets.default
): Promise<void> => {
  return new Promise((resolve) => {
    if (prefersReducedMotion()) {
      Object.assign(element.style, properties);
      resolve();
      return;
    }

    const { stiffness = 170, damping = 26, mass = 1 } = config;
    
    // Calculate duration based on spring parameters
    const duration = Math.sqrt(mass / stiffness) * damping * 10;
    
    element.style.transition = `all ${duration}ms cubic-bezier(0.34, 1.56, 0.64, 1)`;
    Object.assign(element.style, properties);
    
    setTimeout(() => {
      element.style.transition = '';
      resolve();
    }, duration);
  });
};

/**
 * Fade in animation
 */
export const fadeIn = (
  element: HTMLElement,
  duration: number = durations.normal
): Promise<void> => {
  return new Promise((resolve) => {
    if (prefersReducedMotion()) {
      element.style.opacity = '1';
      resolve();
      return;
    }

    element.style.opacity = '0';
    element.style.transition = `opacity ${duration}ms ${easings.easeOut}`;
    
    requestAnimationFrame(() => {
      element.style.opacity = '1';
      setTimeout(() => {
        element.style.transition = '';
        resolve();
      }, duration);
    });
  });
};

/**
 * Fade out animation
 */
export const fadeOut = (
  element: HTMLElement,
  duration: number = durations.normal
): Promise<void> => {
  return new Promise((resolve) => {
    if (prefersReducedMotion()) {
      element.style.opacity = '0';
      resolve();
      return;
    }

    element.style.transition = `opacity ${duration}ms ${easings.easeIn}`;
    element.style.opacity = '0';
    
    setTimeout(() => {
      element.style.transition = '';
      resolve();
    }, duration);
  });
};

/**
 * Slide in animation
 */
export const slideIn = (
  element: HTMLElement,
  direction: 'top' | 'bottom' | 'left' | 'right' = 'bottom',
  duration: number = durations.normal
): Promise<void> => {
  return new Promise((resolve) => {
    if (prefersReducedMotion()) {
      element.style.transform = 'translate(0, 0)';
      element.style.opacity = '1';
      resolve();
      return;
    }

    const transforms = {
      top: 'translateY(-20px)',
      bottom: 'translateY(20px)',
      left: 'translateX(-20px)',
      right: 'translateX(20px)',
    };

    element.style.transform = transforms[direction];
    element.style.opacity = '0';
    element.style.transition = `transform ${duration}ms ${easings.spring}, opacity ${duration}ms ${easings.easeOut}`;
    
    requestAnimationFrame(() => {
      element.style.transform = 'translate(0, 0)';
      element.style.opacity = '1';
      
      setTimeout(() => {
        element.style.transition = '';
        resolve();
      }, duration);
    });
  });
};

/**
 * Scale in animation
 */
export const scaleIn = (
  element: HTMLElement,
  duration: number = durations.normal
): Promise<void> => {
  return new Promise((resolve) => {
    if (prefersReducedMotion()) {
      element.style.transform = 'scale(1)';
      element.style.opacity = '1';
      resolve();
      return;
    }

    element.style.transform = 'scale(0.95)';
    element.style.opacity = '0';
    element.style.transition = `transform ${duration}ms ${easings.spring}, opacity ${duration}ms ${easings.easeOut}`;
    
    requestAnimationFrame(() => {
      element.style.transform = 'scale(1)';
      element.style.opacity = '1';
      
      setTimeout(() => {
        element.style.transition = '';
        resolve();
      }, duration);
    });
  });
};

/**
 * Stagger animation for lists
 */
export const staggerAnimation = async (
  elements: HTMLElement[],
  animationFn: (element: HTMLElement) => Promise<void>,
  staggerDelay: number = 50
): Promise<void> => {
  for (let i = 0; i < elements.length; i++) {
    const delay = getStaggerDelay(i, staggerDelay);
    await new Promise((resolve) => setTimeout(resolve, delay));
    await animationFn(elements[i]);
  }
};

/**
 * Ripple effect animation
 */
export const rippleEffect = (
  element: HTMLElement,
  x: number,
  y: number
): void => {
  if (prefersReducedMotion()) return;

  const ripple = document.createElement('span');
  const rect = element.getBoundingClientRect();
  
  ripple.style.position = 'absolute';
  ripple.style.width = '20px';
  ripple.style.height = '20px';
  ripple.style.borderRadius = '50%';
  ripple.style.background = 'rgba(255, 255, 255, 0.5)';
  ripple.style.left = `${x - rect.left}px`;
  ripple.style.top = `${y - rect.top}px`;
  ripple.style.transform = 'translate(-50%, -50%) scale(0)';
  ripple.style.pointerEvents = 'none';
  ripple.style.animation = `ripple ${durations.slow}ms ${easings.easeOut}`;
  
  element.appendChild(ripple);
  
  setTimeout(() => {
    ripple.remove();
  }, durations.slow);
};

/**
 * Smooth scroll to element
 */
export const smoothScrollTo = (
  element: HTMLElement,
  offset: number = 0
): void => {
  if (prefersReducedMotion()) {
    element.scrollIntoView();
    return;
  }

  const targetPosition = element.getBoundingClientRect().top + window.pageYOffset - offset;
  
  window.scrollTo({
    top: targetPosition,
    behavior: 'smooth',
  });
};

/**
 * React hook for animation on mount
 */
export const useAnimateOnMount = (
  animationType: 'fade' | 'slide' | 'scale' = 'fade',
  direction?: 'top' | 'bottom' | 'left' | 'right'
) => {
  return {
    initial: {
      opacity: 0,
      ...(animationType === 'slide' && {
        transform: direction === 'top' ? 'translateY(-20px)' :
                   direction === 'bottom' ? 'translateY(20px)' :
                   direction === 'left' ? 'translateX(-20px)' :
                   direction === 'right' ? 'translateX(20px)' : 'translateY(20px)',
      }),
      ...(animationType === 'scale' && {
        transform: 'scale(0.95)',
      }),
    },
    animate: {
      opacity: 1,
      transform: animationType === 'fade' ? undefined : 
                animationType === 'slide' ? 'translate(0, 0)' :
                'scale(1)',
    },
    transition: {
      duration: prefersReducedMotion() ? 0 : durations.normal / 1000,
      ease: easings.spring,
    },
  };
};

export default {
  springPresets,
  easings,
  durations,
  prefersReducedMotion,
  getAnimationDuration,
  getStaggerDelay,
  animateSpring,
  fadeIn,
  fadeOut,
  slideIn,
  scaleIn,
  staggerAnimation,
  rippleEffect,
  smoothScrollTo,
  useAnimateOnMount,
};
