PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS OFCHandAudit (
    HandID TEXT PRIMARY KEY,
    RawName TEXT NOT NULL DEFAULT '',
    Actor_ID TEXT NOT NULL DEFAULT 'UNKNOWN',
    NameQuality TEXT NOT NULL DEFAULT '',
    HeroChair INTEGER NOT NULL DEFAULT -1,
    OpponentChair INTEGER NOT NULL DEFAULT -1,
    DealerChair INTEGER NOT NULL DEFAULT -1,
    HighestRoundSeen INTEGER NOT NULL DEFAULT -1,
    RevealMask INTEGER NOT NULL DEFAULT 0,
    RevealCount INTEGER NOT NULL DEFAULT 0,
    HeroResultFantasy INTEGER NOT NULL DEFAULT 0,
    OpponentResultFantasy INTEGER NOT NULL DEFAULT 0,
    ResultFrame TEXT NOT NULL DEFAULT '',
    Status TEXT NOT NULL DEFAULT 'UNRECONSTRUCTED',
    Reason TEXT NOT NULL DEFAULT '',
    SourceSchema TEXT NOT NULL DEFAULT '',
    LastEmittedLocal TEXT NOT NULL DEFAULT '',
    Last_Updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS OFCReconstructedActions (
    Action_ID INTEGER PRIMARY KEY AUTOINCREMENT,
    HandID TEXT NOT NULL,
    Actor_ID TEXT NOT NULL,
    RawName TEXT NOT NULL DEFAULT '',
    NameQuality TEXT NOT NULL DEFAULT '',
    OpponentChair INTEGER NOT NULL,
    DealerChair INTEGER NOT NULL,
    IsDealer INTEGER NOT NULL,
    RoundIndex INTEGER NOT NULL,
    IncomingCards TEXT NOT NULL DEFAULT '',
    AddedTop TEXT NOT NULL DEFAULT '',
    AddedMiddle TEXT NOT NULL DEFAULT '',
    AddedBottom TEXT NOT NULL DEFAULT '',
    DiscardCard TEXT NOT NULL DEFAULT '',
    HeroPublicTop TEXT NOT NULL DEFAULT '',
    HeroPublicMiddle TEXT NOT NULL DEFAULT '',
    HeroPublicBottom TEXT NOT NULL DEFAULT '',
    OpponentBoardTop TEXT NOT NULL DEFAULT '',
    OpponentBoardMiddle TEXT NOT NULL DEFAULT '',
    OpponentBoardBottom TEXT NOT NULL DEFAULT '',
    Evidence TEXT NOT NULL DEFAULT '',
    Confidence TEXT NOT NULL DEFAULT 'UNREVIEWED',
    ActionStatsEligible INTEGER NOT NULL DEFAULT 0,
    StatsEligibleReason TEXT NOT NULL DEFAULT '',
    ResultFrame TEXT NOT NULL DEFAULT '',
    Created_At TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(HandID, RoundIndex),
    FOREIGN KEY(HandID) REFERENCES OFCHandAudit(HandID) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ofc_actions_actor_round
ON OFCReconstructedActions(Actor_ID, RoundIndex, IsDealer, ActionStatsEligible);

CREATE INDEX IF NOT EXISTS idx_ofc_handaudit_actor
ON OFCHandAudit(Actor_ID, Status);

CREATE VIEW IF NOT EXISTS OFCOpponentCoverage AS
SELECT
    Actor_ID,
    RoundIndex,
    IsDealer,
    COUNT(*) AS Opportunities,
    SUM(ActionStatsEligible) AS EligibleActions,
    COUNT(DISTINCT HandID) AS Hands
FROM OFCReconstructedActions
GROUP BY Actor_ID, RoundIndex, IsDealer;
