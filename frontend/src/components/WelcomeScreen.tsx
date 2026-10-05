interface WelcomeScreenProps {
  onSuggestionClick: (question: string) => void;
}

function WelcomeScreen({
  onSuggestionClick,
}: WelcomeScreenProps) {
  return (
    <div className="welcome-screen">

      {/* Welcome Icon */}
      <div className="welcome-icon">
        ✦
      </div>

      {/* Heading */}
      <h1 className="welcome-title">
        Welcome to Campus AI
      </h1>

      <p className="welcome-description">
        Your AI-powered assistant for SIES Graduate School
        of Technology. Ask questions about academics,
        syllabus, notices and college information.
      </p>

      {/* Suggestion Cards */}
      <div className="suggestions">

        <div
          className="suggestion-card"
          onClick={() =>
            onSuggestionClick(
              "What is the SIES GST syllabus?"
            )
          }
        >
          <div className="suggestion-icon">
            📚
          </div>

          <div className="suggestion-title">
            Syllabus
          </div>

          <div className="suggestion-description">
            Find subjects and syllabus information
          </div>
        </div>


        <div
          className="suggestion-card"
          onClick={() =>
            onSuggestionClick(
              "Show me important SIES college notices"
            )
          }
        >
          <div className="suggestion-icon">
            📢
          </div>

          <div className="suggestion-title">
            Notices
          </div>

          <div className="suggestion-description">
            Search important college notices
          </div>
        </div>


        <div
          className="suggestion-card"
          onClick={() =>
            onSuggestionClick(
              "Tell me about SIES academic information"
            )
          }
        >
          <div className="suggestion-icon">
            🎓
          </div>

          <div className="suggestion-title">
            Academics
          </div>

          <div className="suggestion-description">
            Ask about academic information
          </div>
        </div>


        <div
          className="suggestion-card"
          onClick={() =>
            onSuggestionClick(
              "What is SIES Graduate School of Technology?"
            )
          }
        >
          <div className="suggestion-icon">
            🏫
          </div>

          <div className="suggestion-title">
            About SIES GST
          </div>

          <div className="suggestion-description">
            Learn about SIES Graduate School of Technology
          </div>
        </div>

      </div>

    </div>
  );
}

export default WelcomeScreen;