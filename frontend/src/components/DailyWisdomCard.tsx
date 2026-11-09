import React from 'react';
import { Sparkles } from 'lucide-react';

const REFLECTIONS = [
  {
    reference: 'Bhagavad Gita 2.47',
    verse: 'कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।',
    meaning: 'Focus on the work you can do; let go of trying to control every outcome.',
  },
  {
    reference: 'Bhagavad Gita 2.48',
    verse: 'योगस्थः कुरु कर्माणि सङ्गं त्यक्त्वा धनञ्जय।',
    meaning: 'Meet success and setbacks with steadiness, and keep acting with care.',
  },
  {
    reference: 'Bhagavad Gita 2.14',
    verse: 'मात्रास्पर्शास्तु कौन्तेय शीतोष्णसुखदुःखदाः।',
    meaning: 'Difficult feelings and pleasant moments both pass; patience helps us meet them.',
  },
  {
    reference: 'Bhagavad Gita 6.5',
    verse: 'उद्धरेदात्मनात्मानं नात्मानमवसादयेत्।',
    meaning: 'Support your own growth with steady effort; do not let discouragement define you.',
  },
  {
    reference: 'Bhagavad Gita 4.7',
    verse: 'यदा यदा हि धर्मस्य ग्लानिर्भवति भारत।',
    meaning: 'When things feel out of balance, choose a small action that restores what is right.',
  },
];

export const DailyWisdomCard: React.FC = () => {
  const day = Math.floor(Date.now() / 86_400_000);
  const reflection = REFLECTIONS[day % REFLECTIONS.length];

  return (
    <section className="wisdom-card" aria-label="Daily Gita reflection">
      <div className="wisdom-heading">
        <Sparkles className="h-3.5 w-3.5" />
        <span>VICHAR OF THE DAY</span>
        <span className="wisdom-reference">{reflection.reference}</span>
      </div>
      <p className="wisdom-verse" lang="sa">{reflection.verse}</p>
      <p className="wisdom-meaning">{reflection.meaning}</p>
      <p className="wisdom-note">Practical reflection · meaning paraphrased</p>
    </section>
  );
};
